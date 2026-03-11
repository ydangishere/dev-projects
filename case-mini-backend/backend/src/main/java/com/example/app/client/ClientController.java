package com.example.app.client;

import com.example.app.client.dto.ClientResponse;
import com.example.app.client.dto.ClientUpdateRequest;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/clients")
public class ClientController {
    private final ClientService service;

    public ClientController(ClientService service) {
        this.service = service;
    }

    @GetMapping
    public List<ClientResponse> search(@RequestParam String search) {
        return service.searchByName(search);
    }

    @PatchMapping("/{id}")
    public ClientResponse updateAge(@PathVariable Long id, @RequestBody ClientUpdateRequest req) {
        return service.updateAge(id, req.age());
    }
}