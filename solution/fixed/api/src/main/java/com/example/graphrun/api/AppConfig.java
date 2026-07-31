package com.example.graphrun.api;

import com.example.graphrun.mlflow.SchemaLocator;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties(GraphRunProperties.class)
public class AppConfig {

    @Bean
    SchemaLocator schemaLocator(GraphRunProperties properties) {
        return new SchemaLocator(properties.mlflowCache());
    }
}
