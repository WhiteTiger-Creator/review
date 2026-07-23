package verify

import (
	"fmt"
	"io"
	"os"
	"sort"
	"strconv"
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
	if err := requireExactInventory(root, item); err != nil {
		return nil, cryptoutil.Certificate{}, err
	}
	results := make([]EvidencePulse, 0, item.LastPulse-item.FirstPulse+1)
	for index := item.FirstPulse; index <= item.LastPulse; index++ {
		name := fmt.Sprintf("pulse-%d.json", index)
		data, err := readRegularAt(root, name)
		if err != nil {
			return nil, cryptoutil.Certificate{}, err
		}
		if cryptoutil.SHA512(data) != item.PulseSHA512[strconv.FormatUint(index, 10)] {
			return nil, cryptoutil.Certificate{}, fmt.Errorf("evidence %s does not match its case SHA-512 pin", name)
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
	if cryptoutil.SHA512(certificateBytes) != item.CertificateSHA512 {
		return nil, cryptoutil.Certificate{}, fmt.Errorf("certificate evidence does not match its case SHA-512 pin")
	}
	certificate, err := cryptoutil.ParseCertificate(certificateBytes)
	if err != nil {
		return nil, cryptoutil.Certificate{}, err
	}
	return results, certificate, nil
}

func openEvidenceDirectory(path string) (*os.File, error) {
	info, err := os.Lstat(path)
	if err != nil {
		return nil, fmt.Errorf("inspect %s: %w", path, err)
	}
	if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return nil, fmt.Errorf("evidence directory is not a regular directory")
	}
	fd, err := syscall.Open(path, syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0)
	if err != nil {
		return nil, fmt.Errorf("open evidence directory: %w", err)
	}
	return os.NewFile(uintptr(fd), path), nil
}

func requireExactInventory(root *os.File, item model.Case) error {
	names, err := root.Readdirnames(-1)
	if err != nil {
		return fmt.Errorf("list evidence directory: %w", err)
	}
	expected := make([]string, 0, item.LastPulse-item.FirstPulse+2)
	expected = append(expected, "certificate.pem")
	for index := item.FirstPulse; index <= item.LastPulse; index++ {
		expected = append(expected, fmt.Sprintf("pulse-%d.json", index))
	}
	sort.Strings(names)
	sort.Strings(expected)
	if len(names) != len(expected) {
		return fmt.Errorf("evidence directory contains unexpected or missing entries")
	}
	for index := range names {
		if names[index] != expected[index] {
			return fmt.Errorf("evidence directory contains unexpected or missing entries")
		}
	}
	return nil
}

func readRegularAt(root *os.File, name string) ([]byte, error) {
	fd, err := syscall.Openat(int(root.Fd()), name, syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0)
	if err != nil {
		return nil, fmt.Errorf("open evidence %s: %w", name, err)
	}
	file := os.NewFile(uintptr(fd), name)
	defer file.Close()
	info, err := file.Stat()
	if err != nil || !info.Mode().IsRegular() {
		return nil, fmt.Errorf("evidence %s is not a regular file", name)
	}
	data, err := io.ReadAll(io.LimitReader(file, (2<<20)+1))
	if err != nil {
		return nil, fmt.Errorf("read evidence %s: %w", name, err)
	}
	if len(data) > 2<<20 {
		return nil, fmt.Errorf("evidence %s exceeds 2097152 bytes", name)
	}
	return data, nil
}
