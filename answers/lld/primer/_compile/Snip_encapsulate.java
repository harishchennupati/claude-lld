import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_encapsulate {
// asking (train wreck) vs telling
static class City { final String name; City(String n) { name = n; } }
static class Address { final City city; Address(City c) { city = c; } }
static class Customer { final Address address; Customer(Address a) { address = a; } }
static class Order {
    private final Customer customer; Order(Customer c) { customer = c; }
    String shipCity() { return customer.address.city.name; }        // Order knows its own shape; callers ask Order
    boolean shipsTo(String city) { return shipCity().equals(city); } // tell, don't ask
}
}
