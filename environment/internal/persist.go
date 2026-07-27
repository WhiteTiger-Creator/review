package internal

// PersistTips persists tip state for the active evaluation run.
func (l *Ledger) PersistTips() {
	if l == nil {
		return
	}
	SoftPersist(l.Root, l.Out, l.gen)
}
