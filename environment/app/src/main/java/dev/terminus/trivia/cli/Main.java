package dev.terminus.trivia.cli;

import picocli.CommandLine;

public final class Main {
    public static void main(String[] args) {
        int code = new CommandLine(new MainCommand())
                .setCaseInsensitiveEnumValuesAllowed(true)
                .execute(args);
        System.exit(code);
    }

    @CommandLine.Command(name = "trivia-dungeon", mixinStandardHelpOptions = true,
            subcommands = {AuditCommand.class, PlaythroughCommand.class},
            description = "Terminal trivia dungeon auditor and playthrough verifier")
    static final class MainCommand implements Runnable {
        @Override
        public void run() {
            CommandLine.usage(this, System.out);
        }
    }
}
