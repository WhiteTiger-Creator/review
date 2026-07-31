plugins {
    id("org.springframework.boot") version "3.3.5"
    application
}

dependencies {
    implementation(project(":core"))
    implementation("com.fasterxml.jackson.core:jackson-databind")
    implementation("com.fasterxml.jackson.datatype:jackson-datatype-jsr310")
}

application {
    mainClass.set("com.example.graphrun.manifest.ManifestCliMain")
}

tasks.bootJar {
    archiveFileName.set("cli.jar")
}
