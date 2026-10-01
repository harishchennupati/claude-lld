// Whose budget a request spends: one counter per customer, per IP, per customer per endpoint,
// or one shared by everyone.
// Why an enum: a closed set of four. keyFor() switches over it, and the compiler flags a missing
// case.
enum CountPer {
    CUSTOMER, IP, CUSTOMER_AND_ENDPOINT, EVERYONE
}
