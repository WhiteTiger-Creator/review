plugins {
    application
    java
}

group = "com.example.releasemirror"
version = "0.1.0"

repositories {
    mavenCentral()
}

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(21))
    }
}

application {
    mainClass.set("com.example.releasemirror.ReleaseMirrorMain")
}

tasks.jar {
    archiveFileName.set("release-mirror.jar")
    manifest {
        attributes["Main-Class"] = "com.example.releasemirror.ReleaseMirrorMain"
    }
    duplicatesStrategy = DuplicatesStrategy.EXCLUDE
    from(sourceSets.main.get().output)
    from({
        configurations.runtimeClasspath.get()
            .filter { it.name.endsWith("jar") }
            .map { zipTree(it) }
    })
}
