package demo.vietpay;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.*;
import org.springframework.web.client.RestClient;
import org.springframework.kafka.core.KafkaTemplate;
import jakarta.persistence.*;
import java.util.*;

@SpringBootApplication
public class LendingApplication {
  public static void main(String[] args) { SpringApplication.run(LendingApplication.class, args); }
}

@Entity class Deal {
  @Id @GeneratedValue(strategy=GenerationType.IDENTITY) public Long id;
  public String title;
  public Long amount;
}
@Entity class Application {
  @Id @GeneratedValue(strategy=GenerationType.IDENTITY) public Long id;
  public Long dealId;
  public String borrowerAlias;
  public String status = "APPLIED";
  @Column(length=4000) public String analysis;
}
interface Deals extends JpaRepository<Deal,Long> {}
interface Applications extends JpaRepository<Application,Long> {}

@RestController
class LendingController {
  private final Deals deals;
  private final Applications applications;
  private final KafkaTemplate<String,String> kafka;
  private final RestClient ai;
  LendingController(Deals d, Applications a, KafkaTemplate<String,String> k) {
    deals=d; applications=a; kafka=k;
    ai=RestClient.builder().baseUrl(System.getenv().getOrDefault("AI_URL","http://localhost:8001")).build();
  }
  void event(Application a, String type) {
    try { kafka.send("lending.events",a.id.toString(),"{\"application_id\":"+a.id+",\"event\":\""+type+"\"}"); }
    catch(Exception e) { System.err.println("Demo event publish failed: "+e.getMessage()); }
  }
  @GetMapping("/deals") List<Deal> list() {return deals.findAll();}
  @PostMapping("/deals") Deal deal(@RequestBody Deal d) {
    if(d.amount==null || d.amount<=0 || d.title==null || d.title.isBlank()) throw new IllegalArgumentException("Invalid deal");
    d.id=null; return deals.save(d);
  }
  @PostMapping("/applications") Application apply(@RequestBody Application a) {
    if(a.dealId==null || !deals.existsById(a.dealId)) throw new IllegalArgumentException("Unknown deal");
    if(a.borrowerAlias==null || a.borrowerAlias.isBlank()) throw new IllegalArgumentException("Missing borrower");
    a.id=null; a.status="APPLIED"; a.analysis=null;
    Application saved=applications.save(a); event(saved,"APPLIED"); return saved;
  }
  @GetMapping("/applications/{id}") Application get(@PathVariable Long id) {return require(id);}
  Application require(Long id) {return applications.findById(id).orElseThrow(()->new NoSuchElementException("Application not found"));}
  Application transition(Long id,String from,String to) {
    Application a=require(id);
    if(!a.status.equals(from)) throw new IllegalStateException("Expected "+from+"; got "+a.status);
    a.status=to; a=applications.save(a); event(a,to); return a;
  }
  @PostMapping("/applications/{id}/verify") Application verify(@PathVariable Long id) {
    return transition(id,"APPLIED","DEMO_VERIFIED");
  }
  @PostMapping("/applications/{id}/analyze") Application analyze(@PathVariable Long id) {
    Application a=require(id);
    if(!a.status.equals("DEMO_VERIFIED")) throw new IllegalStateException("Verify first");
    Map<?,?> result=ai.post().uri("/analyze").body(Map.of("application_id",id,"borrower_alias",a.borrowerAlias)).retrieve().body(Map.class);
    a.analysis=String.valueOf(result);
    a.status="REVIEW_REQUIRED"; a=applications.save(a); event(a,"REVIEW_REQUIRED"); return a;
  }
  @PostMapping("/applications/{id}/approve") Application approve(@PathVariable Long id,@RequestHeader(value="X-Demo-Reviewer",required=false) String reviewer) {
    if(!"approved".equals(reviewer)) throw new IllegalStateException("Demo human reviewer confirmation required");
    return transition(id,"REVIEW_REQUIRED","CONTRACT_DRAFTED");
  }
  @PostMapping("/applications/{id}/sign") Application sign(@PathVariable Long id) {return transition(id,"CONTRACT_DRAFTED","DEMO_SIGNED");}
  @PostMapping("/applications/{id}/disburse") Application disburse(@PathVariable Long id) {return transition(id,"DEMO_SIGNED","DEMO_DISBURSED");}
  @PostMapping("/applications/{id}/monitor") Application monitor(@PathVariable Long id) {return transition(id,"DEMO_DISBURSED","MONITORING");}
  @ExceptionHandler({IllegalArgumentException.class,IllegalStateException.class,NoSuchElementException.class})
  ResponseEntity<Map<String,String>> error(Exception e) {return ResponseEntity.badRequest().body(Map.of("error",e.getMessage()));}
}
