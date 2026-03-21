package com.sso.appa.config;

import com.sso.appa.filter.JwtFilter;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class WebConfig {

    @Bean
    public JwtFilter jwtFilter(JwtProperties jwtProperties) {
        return new JwtFilter(jwtProperties);
    }
}
