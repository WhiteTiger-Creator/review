package main

import (
	"flag"
	"fmt"
	"os"

	"trustremediator/internal/output"
	"trustremediator/internal/pki"
	"trustremediator/internal/policy"
	"trustremediator/internal/provenance"
	"trustremediator/internal/truststore"
	"trustremediator/internal/warrant"
)

func main() {
	incident := flag.String("incident", "", "incident evidence directory")
	writeDir := flag.String("write", "", "output directory")
	flag.Parse()
	if *incident == "" || *writeDir == "" {
		fmt.Fprintf(os.Stderr, "usage: trust_attest --incident <dir> --write <dir>\n")
		os.Exit(1)
	}
	dataDir := *incident
	outDir := *writeDir
	if err := os.MkdirAll(outDir, 0755); err != nil {
		panic(err)
	}

	policyDoc, err := policy.Load(dataDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read policy: %v\n", err)
		os.Exit(1)
	}

	minD, maxD, perr := policy.ChainDepths(policyDoc)
	if perr != nil {
		_ = policy.WriteRejected(outDir, policyDoc)
		os.Exit(2)
	}
	if minD > maxD {
		_ = policy.WriteRejected(outDir, policyDoc)
		os.Exit(2)
	}

	base, _, err := truststore.Load(dataDir)
	if err != nil {
		panic(err)
	}

	eff, patchSummary := warrant.BuildPatch(dataDir, base)
	prov := provenance.Build(dataDir)
	verdicts := pki.ValidateCerts(dataDir, eff)

	if err := policy.WriteRoundtrip(outDir, policyDoc); err != nil {
		panic(err)
	}
	if err := output.WriteSQL(outDir, patchSummary.SQL); err != nil {
		panic(err)
	}
	if err := output.CopyAndApplyPatch(dataDir, outDir, patchSummary.SQL); err != nil {
		panic(err)
	}
	if err := output.WriteAccessTSV(outDir, prov); err != nil {
		panic(err)
	}
	if err := output.WriteCertTSV(outDir, verdicts); err != nil {
		panic(err)
	}
	if err := output.WriteReceipt(outDir, patchSummary); err != nil {
		panic(err)
	}
}
