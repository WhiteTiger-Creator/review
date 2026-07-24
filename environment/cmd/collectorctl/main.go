package main

import (
    "encoding/json"
    "flag"
    "fmt"
    "os"

    "example.com/telemetry-collector-authority/internal/audit"
)

func main() {
    if len(os.Args) < 2 {
        usage()
        os.Exit(2)
    }
    switch os.Args[1] {
    case "manifest":
        cmd := flag.NewFlagSet("manifest", flag.ExitOnError)
        root := cmd.String("root", "/app/environment", "environment root")
        out := cmd.String("out", "", "manifest output path")
        _ = cmd.Parse(os.Args[2:])
        if err := audit.WriteManifest(*root, *out); err != nil {
            fmt.Fprintln(os.Stderr, err)
            os.Exit(1)
        }
    case "lifecycle":
        cmd := flag.NewFlagSet("lifecycle", flag.ExitOnError)
        root := cmd.String("root", "/app/environment", "environment root")
        report := cmd.String("report", "/app/output/collector-compliance-report.json", "report output path")
        trace := cmd.String("trace", "/app/output/collector-runtime-trace.json", "trace output path")
        jsonOut := cmd.Bool("json", false, "write report to stdout")
        _ = cmd.Parse(os.Args[2:])
        value, err := audit.BuildReport(*root, *report, *trace)
        if err != nil {
            fmt.Fprintln(os.Stderr, err)
            os.Exit(1)
        }
        if *jsonOut {
            raw, _ := json.MarshalIndent(value, "", "  ")
            fmt.Println(string(raw))
        }
        if !value.OK {
            os.Exit(3)
        }
    case "serve":
        fmt.Println("collectorctl serve: socket activation recorder is compiled for lifecycle observation")
    default:
        usage()
        os.Exit(2)
    }
}

func usage() {
    fmt.Fprintln(os.Stderr, "usage: collectorctl manifest|lifecycle|serve")
}
