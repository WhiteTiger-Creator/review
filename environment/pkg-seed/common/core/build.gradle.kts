plugins {
    `java-library`
}

dependencies {
    api(project(":canon"))
    api(project(":mlflowio"))
    api("com.fasterxml.jackson.core:jackson-databind")
    api("com.fasterxml.jackson.datatype:jackson-datatype-jsr310")
    api("org.yaml:snakeyaml")
}
