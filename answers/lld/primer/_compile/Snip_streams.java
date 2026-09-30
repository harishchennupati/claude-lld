import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_streams {
record Order(String id, int price, long ts) {}
java.util.List<Order> sorted(java.util.List<Order> os) {
    return os.stream()
             .sorted(java.util.Comparator.comparingInt(Order::price).reversed().thenComparingLong(Order::ts))
             .toList();
}
java.util.Map<Integer, java.util.List<Order>> byPrice(java.util.List<Order> os) {
    return os.stream().collect(java.util.stream.Collectors.groupingBy(Order::price));
}
int total(java.util.List<Order> os) { return os.stream().mapToInt(Order::price).sum(); }
}
