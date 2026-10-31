# kotlinx.serialization: keep generated serializers for the API models.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt
-keepclassmembers class kotlinx.serialization.json.** { *** Companion; }
-keepclasseswithmembers class kotlinx.serialization.json.** { kotlinx.serialization.KSerializer serializer(...); }
-keep,includedescriptorclasses class app.yardharvest.manager.**$$serializer { *; }
-keepclassmembers class app.yardharvest.manager.** { *** Companion; }
-keepclasseswithmembers class app.yardharvest.manager.** { kotlinx.serialization.KSerializer serializer(...); }

# Stripe ships its own consumer rules; Terminal needs its model classes intact.
-keep class com.stripe.stripeterminal.** { *; }
-dontwarn com.stripe.**

# OkHttp / Okio platform probes.
-dontwarn okhttp3.internal.platform.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**

# Stripe Terminal's transitive deps reference JVM-only classes Android
# doesn't ship (Jackson's java.beans hooks, slf4j's optional binder).
-dontwarn java.beans.**
-dontwarn org.slf4j.impl.**
# Jackson (inside Terminal) reads its annotations reflectively.
-keepattributes Signature, EnclosingMethod
-keep class com.fasterxml.jackson.annotation.** { *; }
