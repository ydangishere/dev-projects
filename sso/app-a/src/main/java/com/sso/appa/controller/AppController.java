package com.sso.appa.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

@Controller
public class AppController {

    @Value("${app.auth-service-url}")
    private String authServiceUrl;

    @Value("${app.callback-url}")
    private String callbackUrl;

    @GetMapping("/")
    public String home(Authentication auth, HttpServletRequest request) {
        if (auth != null && auth.isAuthenticated()) {
            return "redirect:/dashboard";
        }
        String redirectUri = authServiceUrl + "/?redirect_uri=" + URLEncoder.encode(callbackUrl, StandardCharsets.UTF_8);
        return "redirect:" + redirectUri;
    }

    @GetMapping("/callback")
    public String callback(HttpServletRequest request, HttpServletResponse response) {
        String token = request.getParameter("token");
        if (token == null || token.isBlank()) {
            return "redirect:/";
        }
        Cookie cookie = new Cookie("sso_token", token);
        cookie.setPath("/");
        cookie.setHttpOnly(true);
        cookie.setMaxAge(3600);
        response.addCookie(cookie);
        return "redirect:/dashboard";
    }

    @GetMapping("/dashboard")
    public String dashboard(Authentication auth, Model model, HttpServletRequest request) {
        if (auth == null || !auth.isAuthenticated()) {
            return "redirect:/";
        }
        String displayName = (String) request.getAttribute("displayName");
        model.addAttribute("username", auth.getName());
        model.addAttribute("displayName", displayName != null ? displayName : auth.getName());
        model.addAttribute("appName", "App A");
        return "dashboard";
    }

    @GetMapping("/logout")
    public String logout(HttpServletResponse response) {
        Cookie cookie = new Cookie("sso_token", "");
        cookie.setPath("/");
        cookie.setMaxAge(0);
        response.addCookie(cookie);
        return "redirect:/";
    }
}
