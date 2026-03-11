package com.example.app;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * MAIN APPLICATION - Enable Scheduling for Outbox Publisher
 */
@SpringBootApplication
@EnableScheduling  // Enable @Scheduled methods
public class AppApplication {

	public static void main(String[] args) {
		SpringApplication.run(AppApplication.class, args);
	}

}