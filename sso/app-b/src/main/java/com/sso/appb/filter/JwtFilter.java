package com.sso.appb.filter;

import com.sso.appb.config.JwtProperties;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import javax.crypto.SecretKey;

public class JwtFilter extends OncePerRequestFilter {

    private final JwtProperties jwtProperties;
    private final SecretKey secretKey;

    public JwtFilter(JwtProperties jwtProperties) {
        this.jwtProperties = jwtProperties;
        this.secretKey = Keys.hmacShaKeyFor(jwtProperties.getSecret().getBytes(StandardCharsets.UTF_8));
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String token = getToken(request);

        if (token != null) {
            try {
                Claims claims = Jwts.parser()
                        .verifyWith(secretKey)
                        .build()
                        .parseSignedClaims(token)
                        .getPayload();
                String username = claims.getSubject();
                String displayName = claims.get("displayName", String.class);
                var auth = new UsernamePasswordAuthenticationToken(
                        username,
                        null,
                        Collections.singletonList(new SimpleGrantedAuthority("ROLE_USER"))
                );
                request.setAttribute("displayName", displayName != null ? displayName : username);
                SecurityContextHolder.getContext().setAuthentication(auth);
            } catch (JwtException ignored) {
            }
        }

        filterChain.doFilter(request, response);
    }

    private String getToken(HttpServletRequest request) {
        String tokenParam = request.getParameter("token");
        if (tokenParam != null) return tokenParam;

        Cookie[] cookies = request.getCookies();
        if (cookies != null) {
            for (Cookie c : cookies) {
                if ("sso_token".equals(c.getName())) return c.getValue();
            }
        }
        return null;
    }
}
