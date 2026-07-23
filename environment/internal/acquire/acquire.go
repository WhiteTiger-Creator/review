package acquire

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"beaconaudit/internal/cryptoutil"
	"beaconaudit/internal/model"
)

func Interval(item model.Case, destination string) (err error) {
	stage, err := stageDirectory(destination)
	if err != nil {
		return err
	}
	defer func() {
		if err != nil {
			_ = os.RemoveAll(stage)
		}
	}()
	client := Client(item.APIOrigin)
	certificateID := ""
	for index := item.FirstPulse; index <= item.LastPulse; index++ {
		resource := PulseURL(item.APIOrigin, item.ChainIndex, index)
		data, fetchErr := Fetch(client, resource)
		if fetchErr != nil {
			return fetchErr
		}
		var envelope model.PulseEnvelope
		if jsonErr := json.Unmarshal(data, &envelope); jsonErr != nil {
			return fmt.Errorf("parse pulse %d: %w", index, jsonErr)
		}
		pulse := envelope.Pulse
		if pulse.PulseIndex != index || pulse.ChainIndex != item.ChainIndex || pulse.URI != resource {
			return fmt.Errorf("pulse %d identity does not match requested NIST resource", index)
		}
		if certificateID == "" {
			certificateID = pulse.CertificateID
		}
		if pulse.CertificateID != certificateID {
			return fmt.Errorf("certificate changed inside requested interval")
		}
		if writeErr := writePrivate(filepath.Join(stage, fmt.Sprintf("pulse-%d.json", index)), data); writeErr != nil {
			return writeErr
		}
	}
	certificate, err := Fetch(client, CertificateURL(item.APIOrigin, certificateID))
	if err != nil {
		return err
	}
	parsed, err := cryptoutil.ParseCertificate(certificate)
	if err != nil {
		return err
	}
	if parsed.Fingerprint != strings.ToUpper(certificateID) {
		return fmt.Errorf("downloaded certificate does not match interval certificateId")
	}
	if err = writePrivate(filepath.Join(stage, "certificate.pem"), certificate); err != nil {
		return err
	}
	return ReplaceDirectory(stage, destination)
}
