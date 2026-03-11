package com.example.app.client.dto;

import com.example.app.client.ClientEntity;

public record ClientResponse(Long id, String name, Integer age) {
    public static ClientResponse from(ClientEntity c) {
        return new ClientResponse(c.getId(), c.getName(), c.getAge());
    }
}