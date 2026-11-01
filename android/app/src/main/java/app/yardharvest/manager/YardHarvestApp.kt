package app.yardharvest.manager

import android.app.Application
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ProcessLifecycleOwner
import app.yardharvest.manager.core.AppEnvironment
import app.yardharvest.manager.core.AppLock
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.PushManager
import app.yardharvest.manager.core.TerminalManager
import app.yardharvest.manager.core.TokenStore
import com.stripe.stripeterminal.TerminalApplicationDelegate
import com.stripe.stripeterminal.taptopay.TapToPay

class YardHarvestApp : Application() {
    override fun onCreate() {
        super.onCreate()
        // Stripe runs Tap to Pay in its own process; none of the app's setup
        // belongs there.
        if (TapToPay.isInTapToPayProcess()) return
        TerminalApplicationDelegate.onCreate(this)

        AppEnvironment.init(this)
        TokenStore.init(this)
        Haptics.init(this)
        AppLock.init(this)
        PushManager.init(this)
        TerminalManager.init(this)

        // Only the whole app leaving the foreground arms the lock — not a
        // dialog, the notification shade, or a permission prompt.
        ProcessLifecycleOwner.get().lifecycle.addObserver(object : DefaultLifecycleObserver {
            override fun onStop(owner: LifecycleOwner) = AppLock.shared.didEnterBackground()
            override fun onStart(owner: LifecycleOwner) = AppLock.shared.didBecomeActive()
        })
    }
}
