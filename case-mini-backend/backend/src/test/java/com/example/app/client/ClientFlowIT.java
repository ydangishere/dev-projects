package com.example.app.client;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
class ClientFlowIT {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void searchABC_should_return200() throws Exception {
        mockMvc.perform(get("/api/clients?search=ABC"))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$[0].name").value("ABC"));
    }

    @Test
    void searchEmpty_should_return400() throws Exception {
        mockMvc.perform(get("/api/clients?search="))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("bad_request"))
                .andExpect(jsonPath("$.message").value("search required"));
    }

    @Test
    void updateNonExistentClient_should_return404() throws Exception {
        mockMvc.perform(patch("/api/clients/9999")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"age\":30}"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.error").value("not_found"))
                .andExpect(jsonPath("$.message").value("client not found"));
    }

    @Test
    void updateExistingClient_should_return200() throws Exception {
        mockMvc.perform(patch("/api/clients/1")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"age\":25}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(1))
                .andExpect(jsonPath("$.age").value(25));
    }
}