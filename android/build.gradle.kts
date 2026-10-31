plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.google.services) apply false
}

// The repo lives in a synced folder (OneDrive). Build output is hundreds of
// megabytes of churn that has no business being synced, so a developer can
// point it elsewhere with `yh.buildRoot` in ~/.gradle/gradle.properties.
// CI leaves it unset and builds in place.
providers.gradleProperty("yh.buildRoot").orNull?.let { root ->
    allprojects {
        layout.buildDirectory.set(file("$root/${project.name}"))
    }
}
