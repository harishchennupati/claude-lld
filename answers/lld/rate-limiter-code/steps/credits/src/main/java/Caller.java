// Who a rule is for: signed-in customers only, or anyone, signed in or not.
enum Caller {
    CUSTOMER,   // the request carries an API key
    ANY         // with or without a key (sign-in, the global cap)
}
