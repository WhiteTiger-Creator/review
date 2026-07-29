package pipeline

import (
	"k7w/internal/model"
	"k7w/memo"
	"k7w/slice"
)

func RecordRetry(frame []byte, epoch int, transitionID string) (bool, error) {
	stamp, err := slice.CanonDigest(frame)
	if err != nil {
		return false, err
	}
	var mid model.MemoID
	if h, err := stampHash(stamp); err == nil {
		mid = h
	}
	mid[0] ^= byte(epoch)
	return memo.MarkUnique(mid, model.Transition{ID: transitionID, Code: "retry"})
}

func RecordPack(mid model.MemoID, transitionID, code string) (bool, error) {
	return memo.MarkUnique(mid, model.Transition{ID: transitionID, Code: code})
}

func ResetMemo() {
	memo.ResetLedger()
}

func StampMemoID(stamp string) (model.MemoID, error) {
	return stampHash(stamp)
}
