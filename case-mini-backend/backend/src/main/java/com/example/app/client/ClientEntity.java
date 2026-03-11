package com.example.app.client;

import jakarta.persistence.*;

@Entity
@Table(name = "clients")
public class ClientEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String name;
    private Integer age;

    public Long getId() { return id; }
    public String getName() { return name; }
    public Integer getAge() { return age; }
    public void setName(String name) { this.name = name; }
    public void setAge(Integer age) { this.age = age; }
}