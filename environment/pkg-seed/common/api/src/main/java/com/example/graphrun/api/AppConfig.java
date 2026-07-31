package com.example.graphrun.api;

import com.example.graphrun.mlflow.BundledSchemaValidator;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class AppConfig {

    @Bean
    BundledSchemaValidator bundledSchemaValidator() {
        return new BundledSchemaValidator();
    }
}
