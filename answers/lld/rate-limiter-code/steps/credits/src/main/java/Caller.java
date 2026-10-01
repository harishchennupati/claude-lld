// Who a rule is for: signed-in customers only, or anyone, signed in or not.
// Why an enum: a closed set of two, checked by the compiler, where a string could hold a typo.
enum Caller {
    CUSTOMER,   // the request carries an API key
    ANY         // with or without a key (sign-in, the global cap)
}
