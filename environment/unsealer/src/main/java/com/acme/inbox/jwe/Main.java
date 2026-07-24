package com.acme.inbox.jwe;

/**
 * Entry point of the Acme inbox JWE unsealer.
 *
 * The previous implementation delegated every JOSE and key-agreement operation to a third party
 * library and was removed. Nothing here works yet.
 */
public final class Main {

    private Main() {
    }

    public static void main(String[] args) {
        System.err.println("jwe-unsealer: not implemented");
        System.exit(2);
    }
}
