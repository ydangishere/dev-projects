package com.example.app.client;

import org.springframework.data.jpa.repository.*;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface ClientRepository extends JpaRepository<ClientEntity, Long> {
    @Query("select c from ClientEntity c where lower(c.name) like lower(concat('%', :name, '%'))")
    List<ClientEntity> searchByName(@Param("name") String name);
}