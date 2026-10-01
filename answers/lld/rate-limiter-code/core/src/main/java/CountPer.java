// Whose budget a request spends: one counter per customer, per IP, per customer per endpoint, or
// one shared by everyone.
enum CountPer {
    CUSTOMER, IP, CUSTOMER_AND_ENDPOINT, EVERYONE
}
