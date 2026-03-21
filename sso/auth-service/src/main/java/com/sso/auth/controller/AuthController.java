package com.sso.auth.controller;

import com.sso.auth.entity.User;
import com.sso.auth.repository.UserRepository;
import com.sso.auth.service.JwtService;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.List;

@Controller
public class AuthController {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final List<String> allowedRedirectUris;

    public AuthController(UserRepository userRepository,
                          PasswordEncoder passwordEncoder,
                          JwtService jwtService,
                          @Value("${app.allowed-redirect-uris}") String allowedUris) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
        this.allowedRedirectUris = List.of(allowedUris.split(","));
    }

    @GetMapping("/")
    public String loginPage(@RequestParam(required = false) String redirect_uri,
                           HttpSession session,
                           Model model) {
        if (redirect_uri != null && !redirect_uri.isBlank() && allowedRedirectUris.contains(redirect_uri)) {
            User loggedIn = (User) session.getAttribute("user");
            if (loggedIn != null) {
                String token = jwtService.createToken(loggedIn.getUsername(), loggedIn.getDisplayName());
                return "redirect:" + redirect_uri + (redirect_uri.contains("?") ? "&" : "?") + "token=" + token;
            }
        }
        model.addAttribute("redirectUri", redirect_uri != null ? redirect_uri : "");
        return "login";
    }

    @PostMapping("/auth/login")
    public String login(@RequestParam String username,
                        @RequestParam String password,
                        @RequestParam(required = false) String redirect_uri,
                        HttpSession session,
                        HttpServletResponse response) {
        User user = userRepository.findByUsername(username)
                .orElse(null);
        if (user == null || !passwordEncoder.matches(password, user.getPassword())) {
            return "redirect:/?error=invalid&redirect_uri=" + encode(redirect_uri);
        }

        session.setAttribute("user", user);
        String token = jwtService.createToken(user.getUsername(), user.getDisplayName());

        if (redirect_uri != null && !redirect_uri.isBlank() && allowedRedirectUris.contains(redirect_uri)) {
            return "redirect:" + redirect_uri + (redirect_uri.contains("?") ? "&" : "?") + "token=" + token;
        }

        return "redirect:/?success=logged_in";
    }

    private String encode(String value) {
        return value != null ? URLEncoder.encode(value, StandardCharsets.UTF_8) : "";
    }
}
