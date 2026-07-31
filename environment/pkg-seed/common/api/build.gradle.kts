plugins {
    id("org.springframework.boot") version "3.3.5"
    application
}

dependencies {
    implementation(project(":core"))
    implementation(project(":canon"))
    implementation(project(":mlflowio"))
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("com.fasterxml.jackson.core:jackson-databind")
    implementation("com.fasterxml.jackson.datatype:jackson-datatype-jsr310")
}

application {
    mainClass.set("com.example.graphrun.api.GraphRunSignerApplication")
}

tasks.bootJar {
    archiveFileName.set("api.jar")
}
