import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_dip {
// BEFORE: welded to a concrete class, cannot be tested without a database
static class ReportBefore { private final MySqlRepo repo = new MySqlRepo(); }
static class MySqlRepo { java.util.List<String> all() { return java.util.List.of(); } }
// AFTER: depend on the interface, inject the implementation
interface Repo { java.util.List<String> all(); }
static class Report {
    private final Repo repo;
    Report(Repo repo) { this.repo = repo; }             // constructor injection: valid on construction
    int count() { return repo.all().size(); }
}
static class InMemoryRepo implements Repo { public java.util.List<String> all() { return java.util.List.of("a", "b"); } }
// composition root: new Report(new InMemoryRepo()) in tests, new Report(new SqlRepo()) in prod
}
