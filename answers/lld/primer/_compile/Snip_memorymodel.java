import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_memorymodel {
static class Config {
    private static volatile Config INSTANCE;             // volatile: the write of the fully built object is published
    static Config get() {
        Config c = INSTANCE;
        if (c == null) {
            synchronized (Config.class) {                 // double-checked locking, correct only with volatile
                c = INSTANCE;
                if (c == null) INSTANCE = c = new Config();
            }
        }
        return c;
    }
}
enum Registry { INSTANCE; }                                // the singleton with no such problem at all
}
