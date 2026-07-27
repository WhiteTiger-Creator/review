package com.acme.wallet.sdjwt;

/**
 * Entry point of the wallet presentation broker.
 *
 * <p>The broker reads the wallet configuration, the credential directory and the verifier policy,
 * releases a presentation for every credential the policy allows, and writes the run report. None
 * of that is implemented yet: the previous build called into a third-party SD-JWT library that the
 * platform team has removed from the dependency set.
 */
public final class Main {

    private Main() {
    }

    public static void main(String[] args) {
        System.err.println("sd-jwt-broker: not implemented");
        System.exit(2);
    }
}
