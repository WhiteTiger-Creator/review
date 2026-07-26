package timebridge

/*
#cgo CFLAGS: -I${SRCDIR}/../../libastro/include
#cgo LDFLAGS: -L${SRCDIR}/../../libastro -lastrotime -lm -Wl,-rpath,$ORIGIN/../lib
#include <stdlib.h>
#include "astrotime.h"
*/
import "C"

import (
	"fmt"
	"unsafe"
)

type Table struct{ raw C.leap_table }

func Load(path string) (*Table, error) {
	cpath := C.CString(path)
	defer C.free(unsafe.Pointer(cpath))
	var t Table
	errbuf := make([]byte, 256)
	if C.astro_load_leaps(cpath, &t.raw, (*C.char)(unsafe.Pointer(&errbuf[0])), C.size_t(len(errbuf))) != 0 {
		return nil, fmt.Errorf("%s", cString(errbuf))
	}
	return &t, nil
}
func (t *Table) Close() { C.astro_free_leaps(&t.raw) }
func (t *Table) UTCToTAI(s string) (int64, error) {
	cs := C.CString(s)
	defer C.free(unsafe.Pointer(cs))
	var out C.int64_t
	errbuf := make([]byte, 256)
	if C.astro_utc_to_tai(&t.raw, cs, &out, (*C.char)(unsafe.Pointer(&errbuf[0])), C.size_t(len(errbuf))) != 0 {
		return 0, fmt.Errorf("%s", cString(errbuf))
	}
	return int64(out), nil
}
func (t *Table) TAIToUTC(v int64) (string, error) {
	out := make([]byte, 64)
	errbuf := make([]byte, 256)
	if C.astro_tai_to_utc(&t.raw, C.int64_t(v), (*C.char)(unsafe.Pointer(&out[0])), C.size_t(len(out)), (*C.char)(unsafe.Pointer(&errbuf[0])), C.size_t(len(errbuf))) != 0 {
		return "", fmt.Errorf("%s", cString(errbuf))
	}
	return cString(out), nil
}
func Hermite(y0, m0, y1, m1, t, span float64) float64 {
	return float64(C.astro_hermite(C.double(y0), C.double(m0), C.double(y1), C.double(m1), C.double(t), C.double(span)))
}
func PhaseHermite(y0, m0, y1, m1, t, span float64) float64 {
	return float64(C.astro_phase_hermite(C.double(y0), C.double(m0), C.double(y1), C.double(m1), C.double(t), C.double(span)))
}
func Wrap(v float64) float64 { return float64(C.astro_wrap_degrees(C.double(v))) }
func cString(b []byte) string {
	n := 0
	for n < len(b) && b[n] != 0 {
		n++
	}
	return string(b[:n])
}
