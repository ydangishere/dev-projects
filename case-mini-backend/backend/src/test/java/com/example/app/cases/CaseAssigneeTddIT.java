package com.example.app.cases;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.greaterThan;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.isEmptyOrNullString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
class CaseAssigneeTddIT {

    @Autowired
    private MockMvc mockMvc;

    /**
     * TDD - Red: assignee không tồn tại → phải trả 400
     */
    @Test
    void createCase_invalidAssignee_returns400() throws Exception {
        String body = """
            {
              "title": "TDD Case Invalid Assignee",
              "status": "OPEN"
            }
            """;

        mockMvc.perform(post("/api/cases")
                .param("assigneeId", "999999")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error").value("bad_request"));
    }

    /**
     * TDD - Green: assignee hợp lệ → trả 201 + Location
     */
    @Test
    void createCase_validAssignee_returns201() throws Exception {
        String body = """
            {
              "title": "TDD Case Valid Assignee",
              "status": "OPEN"
            }
            """;

        mockMvc.perform(post("/api/cases")
                .param("assigneeId", "1")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isCreated())
            .andExpect(header().string("Location", not(isEmptyOrNullString())))
            .andExpect(jsonPath("$.id", greaterThan(0)))
            .andExpect(jsonPath("$.title").value("TDD Case Valid Assignee"))
            .andExpect(jsonPath("$.status").value("OPEN"))
            .andExpect(jsonPath("$.assignedPeopleId").value(1));
    }
}
