package com.sso.appb.config;

import com.sso.appb.filter.JwtFilter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class WebConfig {

    @Bean
    public JwtFilter jwtFilter(JwtProperties jwtProperties) {
        return new JwtFilter(jwtProperties);
    }
}
