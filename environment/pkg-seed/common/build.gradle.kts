plugins {
    java
    id("io.spring.dependency-management") version "1.1.6"
}

allprojects {
    group = "com.example.graphrun"
    version = "0.1.0-SNAPSHOT"

    repositories {
        mavenCentral()
    }
}

subprojects {
    apply(plugin = "java")
    apply(plugin = "io.spring.dependency-management")

    java {
        toolchain {
            languageVersion.set(JavaLanguageVersion.of(21))
        }
    }

    dependencyManagement {
        imports {
            mavenBom("org.springframework.boot:spring-boot-dependencies:${property("springBootVersion")}")
        }
        dependencies {
            dependency("com.fasterxml.jackson.core:jackson-databind:${property("jacksonVersion")}")
            dependency("com.fasterxml.jackson.datatype:jackson-datatype-jsr310:${property("jacksonVersion")}")
            dependency("com.networknt:json-schema-validator:${property("jsonSchemaValidatorVersion")}")
            dependency("org.yaml:snakeyaml:${property("snakeyamlVersion")}")
        }
    }

    tasks.withType<Test> {
        useJUnitPlatform()
    }
}
