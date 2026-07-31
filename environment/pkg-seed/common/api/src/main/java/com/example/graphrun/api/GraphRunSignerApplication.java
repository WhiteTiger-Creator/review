package com.example.graphrun.api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties(GraphRunProperties.class)
public class GraphRunSignerApplication {

    public static void main(String[] args) {
        SpringApplication.run(GraphRunSignerApplication.class, args);
    }
}
