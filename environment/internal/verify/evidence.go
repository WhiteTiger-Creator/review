package verify

import (
	"fmt"
	"io"
	"os"
	"syscall"

	"beaconaudit/internal/config"
	"beaconaudit/internal/cryptoutil"
	"beaconaudit/internal/model"
)

type EvidencePulse struct {
	Pulse     model.Pulse
	Filename  string
	RawSHA512 string
}

func LoadEvidence(item model.Case, directory string) ([]EvidencePulse, cryptoutil.Certificate, error) {
	root, err := openEvidenceDirectory(directory)
	if err != nil {
		return nil, cryptoutil.Certificate{}, err
	}
	defer root.Close()
	results := make([]EvidencePulse, 0, item.LastPulse-item.FirstPulse+1)
	for index := item.FirstPulse; index <= item.LastPulse; index++ {
		name := fmt.Sprintf("pulse-%d.json", index)
		data, err := readRegularAt(root, name)
		if err != nil {
			return nil, cryptoutil.Certificate{}, err
		}
		var envelope model.PulseEnvelope
		if err := config.Decode(data, &envelope); err != nil {
			return nil, cryptoutil.Certificate{}, fmt.Errorf("parse %s: %w", name, err)
		}
		results = append(results, EvidencePulse{Pulse: envelope.Pulse, Filename: name, RawSHA512: cryptoutil.SHA512(data)})
	}
	certificateBytes, err := readRegularAt(root, "certificate.pem")
	if err != nil {
		return nil, cryptoutil.Certificate{}, err
	}
	certificate, err := cryptoutil.ParseCertificate(certificateBytes)
	if err != nil {
		return nil, cryptoutil.Certificate{}, err
	}
	return results, certificate, nil
}

func openEvidenceDirectory(path string) (*os.File, error) {
	info, err := os.Stat(path)
	if err != nil {
		return nil, fmt.Errorf("inspect %s: %w", path, err)
	}
	if !info.IsDir() {
		return nil, fmt.Errorf("evidence directory is not a regular directory")
	}
	fd, err := syscall.Open(path, syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_CLOEXEC, 0)
	if err != nil {
		return nil, fmt.Errorf("open evidence directory: %w", err)
	}
	return os.NewFile(uintptr(fd), path), nil
}

func readRegularAt(root *os.File, name string) ([]byte, error) {
	fd, err := syscall.Openat(int(root.Fd()), name, syscall.O_RDONLY|syscall.O_CLOEXEC, 0)
	if err != nil {
		return nil, fmt.Errorf("open evidence %s: %w", name, err)
	}
	file := os.NewFile(uintptr(fd), name)
	defer file.Close()
	info, err := file.Stat()
	if err != nil || !info.Mode().IsRegular() {
		return nil, fmt.Errorf("evidence %s is not a regular file", name)
	}
	data, err := io.ReadAll(file)
	if err != nil {
		return nil, fmt.Errorf("read evidence %s: %w", name, err)
	}
	return data, nil
}
