import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_completable {
java.util.concurrent.ExecutorService io = java.util.concurrent.Executors.newFixedThreadPool(8);
java.util.concurrent.CompletableFuture<String> fetchUser(String id) { return java.util.concurrent.CompletableFuture.supplyAsync(() -> "user:" + id, io); }
java.util.concurrent.CompletableFuture<Integer> fetchLikes(String id) { return java.util.concurrent.CompletableFuture.supplyAsync(() -> 42, io); }
String page(String id) {
    var user = fetchUser(id).orTimeout(300, java.util.concurrent.TimeUnit.MILLISECONDS);
    var likes = fetchLikes(id).exceptionally(e -> 0);                                    // degrade, do not fail the page
    return user.thenCombine(likes, (u, l) -> u + " likes=" + l).join();               // join = get() without checked exception
}
}
