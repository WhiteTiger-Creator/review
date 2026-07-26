package cartographer

// State identity notes for agents reading the starter sources.
// A live state is the occupied coordinate, the set of collected key tags,
// and the set of collapsed crumble coordinates. Keys persist; crumbles
// collapse only after a successful departure.
func stateIdentityDoc() string {
	return "position+keys+collapsed"
}
