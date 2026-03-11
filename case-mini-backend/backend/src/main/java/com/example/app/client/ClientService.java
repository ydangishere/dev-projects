package com.example.app.client;

import com.example.app.client.dto.ClientResponse;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class ClientService {
    private final ClientRepository repo;

    public ClientService(ClientRepository repo) {
        this.repo = repo;
    }

    public List<ClientResponse> searchByName(String search) {
        if (search == null || search.isBlank()) throw new IllegalArgumentException("search required");
        return repo.searchByName(search).stream().map(ClientResponse::from).toList();
    }

    public ClientResponse updateAge(Long id, Integer age) {
        if (age == null || age < 0 || age > 150) throw new IllegalArgumentException("invalid age");

        ClientEntity c = repo.findById(id).orElseThrow(() -> new RuntimeException("client not found"));
        c.setAge(age);
        return ClientResponse.from(repo.save(c));
    }
}