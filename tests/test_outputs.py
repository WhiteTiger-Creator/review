"""Behavior tests for the Hanabi firework championship table."""
import hashlib
import json
import os
from collections import Counter
from typing import ClassVar

OUTPUT = "/app/output"
SCENARIOS = "/app/scenarios"
COLORS = ("R", "Y", "G", "B", "W")

SCENARIO_SHA256 = {
    "s01_simple_hint": "324c8f1ae5944e5f364cee05918b10524f19060ab6896f653cfcfaa3960ac40d",
    "s02_play_success": "0240c20ab6afa54889cb38785cffae05c49b2b63189603598ec094dbe419f89c",
    "s03_play_fail_fuse": "411790dfeb0478bc37f8fc9e6f2200c61b3de8f9c81b5ffc234e85976fa00950",
    "s04_discard_restore": "48a6753d9e649f36c490e4194cc8bf3a3a78b8a8a853c9c6d45a091afa2dc8c0",
    "s05_empty_hint_reject": "864ab389bb77f04dfe228e7b02634fd40f799edb15c3af19d909658a1a0d178f",
    "s06_hint_no_tokens": "5ba2f0a00362a3033362a54e772ffbee78c18d00aad6ac8cbc3e6874ea865008",
    "s07_five_restores_info": "05630d8ae3a759b925be5c85dc9707dfd6b12a16037c0de7ff8063dda61d7a8a",
    "s08_perfect_game": "cb86a908631b99460ad192ed6f9491ce3381637c24cfc9ca259c1fc01317449f",
    "s09_fuse_out": "6648fba3d7ab2e295f6ca4c9dd3cbcc8eefb81e4119cfe31a93b8f8433a33f1f",
    "s10_illegal_then_legal": "12eb15da80774eb2b073a5585ddd9edeb106074ec57273b8ac6cf1f59d605750",
    "s11_deck_end_final": "444c920777c6c9228d7478abbe224f1560d04027cee30e2230aebee447a68f54",
    "s12_discard_at_max_info": "2f403827a80d0b0c10211a5ff861b6e765a29e1792e2298a403af6154716267d",
    "s13_self_hint_reject": "ba074b1a8c577361f0e907e6213e4fbe944a171d6206151c943b174a15b9024b",
    "s14_rank_hint_rotate": "3934a571d37606abbf716fd5d599e5bb47c0f683335566a35ffcd6d2bbff08d9",
    "s15_skip_ahead_fail": "5a319d869036460d37a64a3b0e5a8dc6087a6ac63c663e1da515c1da936ac7f6",
    "s16_five_at_max_info": "b79e30908300aa7a4fcb3140902748ac71cf8dd750328819faf1732d7c2d18b2",
    "s17_hint_play_chain": "95a6a045b1e5a639b867a21ecec7923587d4abfa1d7e5a13362be075c7bcec82",
    "s18_perfect_mid_ownership": "0c5ec3df249b73171d330e030d7429886564f5f655be99728fc7be5affe4405d",
    "s19_deck_end_three": "be5aacccbef305a23a326b311fbede0068c4c62bb7e4b998abdb3d0c94bd3a3c",
    "s20_fuse_beats_deck": "41d0c326398524963233706bf6167e4f8bfca28469c8ed520dc9ba39935aa98d",
    "s21_double_discard": "5562736c821312f7465b1845815e7c7b9d046ce6dd40f60b8767b697679cfb74",
    "s22_empty_rank_hint": "b6725115c23d98f141b4bf4f42b0cb28ebbf0c968c408b4b9edf751fc2f424d7",
    "s23_invalid_hint_target": "0a43cc0f09067755b2f785a92b90aeea8bf3942c99067cf8da173d06ebe3dd29",
    "s24_zero_info_multi": "a6e35a1bbb906d8b2e110293e1b390ed0cd60a3b5d6b9dec4bd22f8876383397",
    "s25_deck_end_wrap": "105ab1e85cb127eede03f73335f012079910308b57c2bf83184e28fe02c73447",
    "s26_deck_end_four": "f2e595db1a33b7e03c4ded4c6a7c7e57da2e62c0e709603f9c9fb726093ed223",
    "s27_perfect_beats_deck": "319f54f409746c0f19e9e4839c91dd5f114095cca0dec9a32d0ce782a2bebef2",
    "s28_hint_fail_discard": "7989bea38f5a791682ab89a227b0f2c9e77c95cb956817c20a8a08fa2560e8f2",
    "s29_multi_reject_hint": "1550dd6f224625c2468a410a8ed821d1e12ca351a9bfe31aee3f958c639ad406",
    "s30_fuse_during_finale": "c25795843e95b987197544083b64a068f4537d1bd01bc7947f3252e427fa3549",
    "s31_five_hint_discard_cap": "09802dfc9b72abd8ff7ed674f0db70e9c681bb5173dc4f61ea0b053699794137",
    "s32_bad_play_index": "314bbf6f381aecfb7e5e9848b669123343c7910361d5fcad02390927bdfe9895",
    "s33_empty_deck_perfect_mid": "04cf1a1169cbe5c27c46950461a846d420d54a199459d72830e6d076f839940b",
    "s34_empty_deck_fuse_priority": "18f446a63f703e5e897399315ccd5d8a58be08c8d135d3c81caf9f8d57b75c18",
    "s35_draw_then_perfect": "61d0d4915bff38e63c370bb2d11f78ef501dafaeff05c1808ae3b0c0348db4c7",
    "s36_draw_then_fuse": "1511344cbf90d99a18a9affc28f7cdd914e0082bf55c12c3fcddb7d2443061a0",
    "s37_hint_during_finale": "8646f0d00ce26ddd45cfe6cc3e37a25af5c59f606ec4590c9c5b6cac9dfcf50b",
    "s38_max_info_finale_discard": "c326384859dc7fdc912fef3714e541dc1e6a6034e6b3a901fda7a780f23fd7c9",
    "s39_five_then_ceiling": "a370cd12988655a62f928d4642cba06a28fbdf70c699176ee9272bff08027dfa",
    "s40_rejects_then_fuse_out": "69787c9373338974542b04ee4354d99d7ebd04620efa5a01e547424c0b4c3c78",
    "s41_hint_reject_cascade": "72a195f54db1495e03cdbd390bd358b7e796f4952cc8763160a7732679d5cf9c",
    "s42_skip_two_ranks": "05701d03b5f1792fca789299f3024e80ca80290575d1646fc70f222e039fc5ad",
    "s43_double_five_restore": "ee96ca3ab302ff6103700432dd38e1448c845535e09f8435ae8be4fc978e3853",
    "s44_three_deck_start2": "be7c13b5ef0889864a9fa2aa0b25ddb3efbc16717b79dde9b0c3f9d5a9f1ab35",
    "s45_four_fuse_finale": "837a7eb1e326af15ef01ddb5163f3382be553750e2202794754e0a6f8998d897",
    "s46_index_shift_play": "e9b06b24cf8b1347bd8ee72b3b550480bbd1fa0b8f634bc8f671b3c96dbf480c",
    "s47_perfect_start1": "dbf5dbb61af4308ae9ec1b40619fc12f00129b7f368959b9518e5d1a5605309c",
    "s48_single_fuse_fail": "a6442a2e9faf21ac30e88a3c4b7ef6caa960b33d24df05b8a347ba2ad50e2a6f",
    "s49_zero_info_chain": "012fd76a3c95ff0409f01e5542b16d97d5d70b1546273163793c4ff955c76508",
    "s50_duplicate_rank_fail": "461dcbb185a93860567f9790038aa789c4dce5fe552f93cfa6bb6f8cdfde7180",
    "s51_one_card_exact_finale": "331a211b6f6489eadda74f9288815b6fc30080b6ab5aa1dc0a1ab75399e1836a",
    "s52_invalid_hint_kind": "e15715804b6e39a75803dc34ade04d4dd54e0d092c615cab2d3be788060a1f98",
    "s53_neg_discard_then_play": "790d98fe664b08ed1f0aff1e50f9c3cc539bb3a81843e2d20685f7426aaa3a95",
    "s54_play_drawn_card": "5c7b753c82f73c3044afd0085b31e0575f84124e7a6326da7e026abe5469fb85",
    "s55_fuse_chain_zero": "ef33ee847ec4bf4e37a7801dad7d1a20aa29b4e64280a76c5d47ead7c3a92184",
    "s56_empty_multi_perfect": "86c256f4b0304849fc8cca8f1033e920af7a3ce36ea7e7d9efe56f25dcb74529",
    "s57_illegal_no_finale_tick": "9077b749b062337f64d6774f47f7aa7c71bc3f50655bc4ab0bbe10f8329213f3",
    "s58_trailing_after_deck_end": "ebf95fad597a62b1df437872555fe655e7f00396c8b1e315d7928e9274523523",
    "s59_uneven_score": "4fd678c97992a00597595d0542b81a6a82aebb73ace1f8e41c0e482e147e0d57",
    "s60_mixed_rejects_discard": "cbfde5416ecba6865ede782a8a66179fc02f1007352af1a44b2343c69b6e1f31",
    "s61_perfect_over_finale": "0720c808205161bf264919a89476b3edf081b0caa6ea963a58df055761aeeb91",
    "s62_five_at_cap_then_hint": "1337b644c890b0aa7bf53832feb124191b88e7010f952bdb89ab0b1efb715036",
}

CONFIG_SHA256 = {
    "config/engine.json": "6f65e8395579f9fdb128a9520c0337a43f4b21734c8684e3a36896135462faae",
    "config/profiles/club_table.toml": "5c2118dc9af8ae27919dda96fa5a6e26095e58b75b7211591cd60165b967da8c",
}

EXPECTED = {
    "s01_simple_hint": {
        "final_info_tokens": 7,
        "final_fuse_tokens": 3,
        "score": 0,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 1,
        "cards_played": 0,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [0],
        "moves_rejected": [],
        "fireworks": {"R": 0, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s02_play_success": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 1,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [0],
        "moves_rejected": [],
        "fireworks": {"R": 1, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s03_play_fail_fuse": {
        "final_info_tokens": 5,
        "final_fuse_tokens": 2,
        "score": 0,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [0],
        "moves_rejected": [],
        "fireworks": {"R": 0, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s04_discard_restore": {
        "final_info_tokens": 7,
        "final_fuse_tokens": 3,
        "score": 1,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 0,
        "cards_discarded": 1,
        "ply_count": 1,
        "moves_applied": [0],
        "moves_rejected": [],
        "fireworks": {"R": 1, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s05_empty_hint_reject": {
        "final_info_tokens": 7,
        "final_fuse_tokens": 3,
        "score": 0,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 1,
        "cards_played": 0,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [1],
        "moves_rejected": [0],
        "fireworks": {"R": 0, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s06_hint_no_tokens": {
        "final_info_tokens": 1,
        "final_fuse_tokens": 3,
        "score": 2,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 0,
        "cards_discarded": 1,
        "ply_count": 1,
        "moves_applied": [1],
        "moves_rejected": [0],
        "fireworks": {"R": 2, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s07_five_restores_info": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 5,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [0],
        "moves_rejected": [],
        "fireworks": {"R": 5, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s08_perfect_game": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 25,
        "game_over": True,
        "end_reason": "perfect",
        "hints_given": 0,
        "cards_played": 5,
        "cards_discarded": 0,
        "ply_count": 5,
        "moves_applied": [0, 1, 2, 3, 4],
        "moves_rejected": [],
        "fireworks": {"R": 5, "Y": 5, "G": 5, "B": 5, "W": 5},
        "final_player": 0,
    },
    "s09_fuse_out": {
        "final_info_tokens": 4,
        "final_fuse_tokens": 0,
        "score": 1,
        "game_over": True,
        "end_reason": "fuse_out",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [0],
        "moves_rejected": [1],
        "fireworks": {"R": 0, "Y": 1, "G": 0, "B": 0, "W": 0},
        "final_player": 0,
    },
    "s10_illegal_then_legal": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 1,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [2],
        "moves_rejected": [0, 1],
        "fireworks": {"R": 1, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s11_deck_end_final": {
        "final_info_tokens": 6,
        "final_fuse_tokens": 3,
        "score": 2,
        "game_over": True,
        "end_reason": "deck_end",
        "hints_given": 0,
        "cards_played": 2,
        "cards_discarded": 1,
        "ply_count": 3,
        "moves_applied": [0, 1, 2],
        "moves_rejected": [3],
        "fireworks": {"R": 1, "Y": 1, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s12_discard_at_max_info": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 3,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 0,
        "cards_discarded": 1,
        "ply_count": 1,
        "moves_applied": [0],
        "moves_rejected": [],
        "fireworks": {"R": 2, "Y": 1, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s13_self_hint_reject": {
        "final_info_tokens": 7,
        "final_fuse_tokens": 3,
        "score": 0,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 1,
        "cards_played": 0,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [1],
        "moves_rejected": [0],
        "fireworks": {"R": 0, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s14_rank_hint_rotate": {
        "final_info_tokens": 4,
        "final_fuse_tokens": 3,
        "score": 1,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 1,
        "cards_played": 0,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [0],
        "moves_rejected": [],
        "fireworks": {"R": 1, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s15_skip_ahead_fail": {
        "final_info_tokens": 6,
        "final_fuse_tokens": 2,
        "score": 1,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [0],
        "moves_rejected": [],
        "fireworks": {"R": 1, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s16_five_at_max_info": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 5,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [0],
        "moves_rejected": [],
        "fireworks": {"R": 5, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s17_hint_play_chain": {
        "final_info_tokens": 3,
        "final_fuse_tokens": 3,
        "score": 2,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 1,
        "cards_played": 2,
        "cards_discarded": 0,
        "ply_count": 3,
        "moves_applied": [0, 1, 2],
        "moves_rejected": [],
        "fireworks": {"R": 1, "Y": 1, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s18_perfect_mid_ownership": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 25,
        "game_over": True,
        "end_reason": "perfect",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [0],
        "moves_rejected": [],
        "fireworks": {"R": 5, "Y": 5, "G": 5, "B": 5, "W": 5},
        "final_player": 2,
    },
    "s19_deck_end_three": {
        "final_info_tokens": 7,
        "final_fuse_tokens": 3,
        "score": 3,
        "game_over": True,
        "end_reason": "deck_end",
        "hints_given": 0,
        "cards_played": 3,
        "cards_discarded": 1,
        "ply_count": 4,
        "moves_applied": [0, 1, 2, 3],
        "moves_rejected": [4],
        "fireworks": {"R": 1, "Y": 1, "G": 1, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s20_fuse_beats_deck": {
        "final_info_tokens": 5,
        "final_fuse_tokens": 0,
        "score": 1,
        "game_over": True,
        "end_reason": "fuse_out",
        "hints_given": 0,
        "cards_played": 2,
        "cards_discarded": 0,
        "ply_count": 2,
        "moves_applied": [0, 1],
        "moves_rejected": [],
        "fireworks": {"R": 1, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s21_double_discard": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 3,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 0,
        "cards_discarded": 2,
        "ply_count": 2,
        "moves_applied": [0, 1],
        "moves_rejected": [],
        "fireworks": {"R": 2, "Y": 1, "G": 0, "B": 0, "W": 0},
        "final_player": 0,
    },
    "s22_empty_rank_hint": {
        "final_info_tokens": 6,
        "final_fuse_tokens": 3,
        "score": 0,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 1,
        "cards_played": 0,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [1],
        "moves_rejected": [0],
        "fireworks": {"R": 0, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s23_invalid_hint_target": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 0,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 0,
        "cards_discarded": 1,
        "ply_count": 1,
        "moves_applied": [2],
        "moves_rejected": [0, 1],
        "fireworks": {"R": 0, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s24_zero_info_multi": {
        "final_info_tokens": 1,
        "final_fuse_tokens": 3,
        "score": 2,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 1,
        "ply_count": 2,
        "moves_applied": [2, 3],
        "moves_rejected": [0, 1],
        "fireworks": {"R": 1, "Y": 1, "G": 0, "B": 0, "W": 0},
        "final_player": 0,
    },
    "s25_deck_end_wrap": {
        "final_info_tokens": 7,
        "final_fuse_tokens": 3,
        "score": 2,
        "game_over": True,
        "end_reason": "deck_end",
        "hints_given": 0,
        "cards_played": 2,
        "cards_discarded": 2,
        "ply_count": 4,
        "moves_applied": [0, 1, 2, 3],
        "moves_rejected": [4, 5],
        "fireworks": {"R": 1, "Y": 1, "G": 0, "B": 0, "W": 0},
        "final_player": 0,
    },
    "s26_deck_end_four": {
        "final_info_tokens": 7,
        "final_fuse_tokens": 3,
        "score": 4,
        "game_over": True,
        "end_reason": "deck_end",
        "hints_given": 0,
        "cards_played": 4,
        "cards_discarded": 1,
        "ply_count": 5,
        "moves_applied": [0, 1, 2, 3, 4],
        "moves_rejected": [5],
        "fireworks": {"R": 1, "Y": 1, "G": 1, "B": 1, "W": 0},
        "final_player": 1,
    },
    "s27_perfect_beats_deck": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 25,
        "game_over": True,
        "end_reason": "perfect",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 2,
        "ply_count": 3,
        "moves_applied": [0, 1, 2],
        "moves_rejected": [],
        "fireworks": {"R": 5, "Y": 5, "G": 5, "B": 5, "W": 5},
        "final_player": 0,
    },
    "s28_hint_fail_discard": {
        "final_info_tokens": 3,
        "final_fuse_tokens": 2,
        "score": 2,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 1,
        "cards_played": 2,
        "cards_discarded": 1,
        "ply_count": 4,
        "moves_applied": [0, 1, 2, 3],
        "moves_rejected": [],
        "fireworks": {"R": 1, "Y": 1, "G": 0, "B": 0, "W": 0},
        "final_player": 0,
    },
    "s29_multi_reject_hint": {
        "final_info_tokens": 7,
        "final_fuse_tokens": 3,
        "score": 0,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 1,
        "cards_played": 0,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [4],
        "moves_rejected": [0, 1, 2, 3],
        "fireworks": {"R": 0, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s30_fuse_during_finale": {
        "final_info_tokens": 5,
        "final_fuse_tokens": 0,
        "score": 1,
        "game_over": True,
        "end_reason": "fuse_out",
        "hints_given": 0,
        "cards_played": 2,
        "cards_discarded": 0,
        "ply_count": 2,
        "moves_applied": [0, 1],
        "moves_rejected": [2],
        "fireworks": {"R": 1, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s31_five_hint_discard_cap": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 5,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 1,
        "cards_played": 1,
        "cards_discarded": 1,
        "ply_count": 3,
        "moves_applied": [0, 1, 2],
        "moves_rejected": [],
        "fireworks": {"R": 5, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s32_bad_play_index": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 1,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [2],
        "moves_rejected": [0, 1],
        "fireworks": {"R": 1, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s33_empty_deck_perfect_mid": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 25,
        "game_over": True,
        "end_reason": "perfect",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [0],
        "moves_rejected": [],
        "fireworks": {"R": 5, "Y": 5, "G": 5, "B": 5, "W": 5},
        "final_player": 1,
    },
    "s34_empty_deck_fuse_priority": {
        "final_info_tokens": 5,
        "final_fuse_tokens": 0,
        "score": 0,
        "game_over": True,
        "end_reason": "fuse_out",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [0],
        "moves_rejected": [1],
        "fireworks": {"R": 0, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 0,
    },
    "s35_draw_then_perfect": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 25,
        "game_over": True,
        "end_reason": "perfect",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 1,
        "ply_count": 2,
        "moves_applied": [0, 1],
        "moves_rejected": [],
        "fireworks": {"R": 5, "Y": 5, "G": 5, "B": 5, "W": 5},
        "final_player": 1,
    },
    "s36_draw_then_fuse": {
        "final_info_tokens": 5,
        "final_fuse_tokens": 0,
        "score": 2,
        "game_over": True,
        "end_reason": "fuse_out",
        "hints_given": 0,
        "cards_played": 2,
        "cards_discarded": 0,
        "ply_count": 2,
        "moves_applied": [0, 1],
        "moves_rejected": [],
        "fireworks": {"R": 1, "Y": 1, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s37_hint_during_finale": {
        "final_info_tokens": 4,
        "final_fuse_tokens": 3,
        "score": 1,
        "game_over": True,
        "end_reason": "deck_end",
        "hints_given": 1,
        "cards_played": 1,
        "cards_discarded": 1,
        "ply_count": 3,
        "moves_applied": [0, 1, 2],
        "moves_rejected": [3, 4],
        "fireworks": {"R": 1, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s38_max_info_finale_discard": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 2,
        "game_over": True,
        "end_reason": "deck_end",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 2,
        "ply_count": 3,
        "moves_applied": [0, 1, 2],
        "moves_rejected": [3],
        "fireworks": {"R": 1, "Y": 1, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s39_five_then_ceiling": {
        "final_info_tokens": 7,
        "final_fuse_tokens": 3,
        "score": 5,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 1,
        "cards_played": 1,
        "cards_discarded": 1,
        "ply_count": 3,
        "moves_applied": [0, 1, 2],
        "moves_rejected": [],
        "fireworks": {"R": 5, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s40_rejects_then_fuse_out": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 0,
        "score": 1,
        "game_over": True,
        "end_reason": "fuse_out",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [3],
        "moves_rejected": [0, 1, 2, 4],
        "fireworks": {"R": 0, "Y": 1, "G": 0, "B": 0, "W": 0},
        "final_player": 0,
    },
    "s41_hint_reject_cascade": {
        "final_info_tokens": 4,
        "final_fuse_tokens": 3,
        "score": 0,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 1,
        "cards_played": 0,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [4],
        "moves_rejected": [0, 1, 2, 3],
        "fireworks": {"R": 0, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s42_skip_two_ranks": {
        "final_info_tokens": 6,
        "final_fuse_tokens": 2,
        "score": 2,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 2,
        "cards_discarded": 0,
        "ply_count": 2,
        "moves_applied": [0, 1],
        "moves_rejected": [],
        "fireworks": {"R": 2, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 0,
    },
    "s43_double_five_restore": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 10,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 2,
        "cards_discarded": 0,
        "ply_count": 2,
        "moves_applied": [0, 1],
        "moves_rejected": [],
        "fireworks": {"R": 5, "Y": 5, "G": 0, "B": 0, "W": 0},
        "final_player": 0,
    },
    "s44_three_deck_start2": {
        "final_info_tokens": 7,
        "final_fuse_tokens": 3,
        "score": 3,
        "game_over": True,
        "end_reason": "deck_end",
        "hints_given": 0,
        "cards_played": 3,
        "cards_discarded": 1,
        "ply_count": 4,
        "moves_applied": [0, 1, 2, 3],
        "moves_rejected": [4, 5],
        "fireworks": {"R": 1, "Y": 1, "G": 1, "B": 0, "W": 0},
        "final_player": 0,
    },
    "s45_four_fuse_finale": {
        "final_info_tokens": 5,
        "final_fuse_tokens": 0,
        "score": 3,
        "game_over": True,
        "end_reason": "fuse_out",
        "hints_given": 0,
        "cards_played": 4,
        "cards_discarded": 0,
        "ply_count": 4,
        "moves_applied": [0, 1, 2, 3],
        "moves_rejected": [],
        "fireworks": {"R": 1, "Y": 1, "G": 1, "B": 0, "W": 0},
        "final_player": 3,
    },
    "s46_index_shift_play": {
        "final_info_tokens": 7,
        "final_fuse_tokens": 3,
        "score": 1,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 2,
        "ply_count": 3,
        "moves_applied": [0, 1, 2],
        "moves_rejected": [],
        "fireworks": {"R": 1, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s47_perfect_start1": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 25,
        "game_over": True,
        "end_reason": "perfect",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [0],
        "moves_rejected": [],
        "fireworks": {"R": 5, "Y": 5, "G": 5, "B": 5, "W": 5},
        "final_player": 1,
    },
    "s48_single_fuse_fail": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 0,
        "score": 2,
        "game_over": True,
        "end_reason": "fuse_out",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [0],
        "moves_rejected": [],
        "fireworks": {"R": 2, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 0,
    },
    "s49_zero_info_chain": {
        "final_info_tokens": 0,
        "final_fuse_tokens": 3,
        "score": 1,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 1,
        "cards_played": 1,
        "cards_discarded": 1,
        "ply_count": 3,
        "moves_applied": [2, 3, 4],
        "moves_rejected": [0, 1],
        "fireworks": {"R": 1, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s50_duplicate_rank_fail": {
        "final_info_tokens": 6,
        "final_fuse_tokens": 2,
        "score": 3,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 2,
        "cards_discarded": 0,
        "ply_count": 2,
        "moves_applied": [0, 1],
        "moves_rejected": [],
        "fireworks": {"R": 3, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 0,
    },
    "s51_one_card_exact_finale": {
        "final_info_tokens": 6,
        "final_fuse_tokens": 3,
        "score": 2,
        "game_over": True,
        "end_reason": "deck_end",
        "hints_given": 0,
        "cards_played": 2,
        "cards_discarded": 1,
        "ply_count": 3,
        "moves_applied": [0, 1, 2],
        "moves_rejected": [3, 4],
        "fireworks": {"R": 1, "Y": 1, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s52_invalid_hint_kind": {
        "final_info_tokens": 7,
        "final_fuse_tokens": 3,
        "score": 0,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 1,
        "cards_played": 0,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [1],
        "moves_rejected": [0],
        "fireworks": {"R": 0, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s53_neg_discard_then_play": {
        "final_info_tokens": 4,
        "final_fuse_tokens": 3,
        "score": 1,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 1,
        "moves_applied": [2],
        "moves_rejected": [0, 1],
        "fireworks": {"R": 1, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s54_play_drawn_card": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 1,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 2,
        "ply_count": 3,
        "moves_applied": [0, 1, 2],
        "moves_rejected": [],
        "fireworks": {"R": 1, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s55_fuse_chain_zero": {
        "final_info_tokens": 5,
        "final_fuse_tokens": 0,
        "score": 0,
        "game_over": True,
        "end_reason": "fuse_out",
        "hints_given": 0,
        "cards_played": 3,
        "cards_discarded": 0,
        "ply_count": 3,
        "moves_applied": [0, 1, 2],
        "moves_rejected": [],
        "fireworks": {"R": 0, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 2,
    },
    "s56_empty_multi_perfect": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 25,
        "game_over": True,
        "end_reason": "perfect",
        "hints_given": 0,
        "cards_played": 5,
        "cards_discarded": 0,
        "ply_count": 5,
        "moves_applied": [0, 1, 2, 3, 4],
        "moves_rejected": [],
        "fireworks": {"R": 5, "Y": 5, "G": 5, "B": 5, "W": 5},
        "final_player": 0,
    },
    "s57_illegal_no_finale_tick": {
        "final_info_tokens": 6,
        "final_fuse_tokens": 3,
        "score": 2,
        "game_over": True,
        "end_reason": "deck_end",
        "hints_given": 0,
        "cards_played": 2,
        "cards_discarded": 1,
        "ply_count": 3,
        "moves_applied": [0, 3, 4],
        "moves_rejected": [1, 2, 5, 6],
        "fireworks": {"R": 1, "Y": 1, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s58_trailing_after_deck_end": {
        "final_info_tokens": 7,
        "final_fuse_tokens": 3,
        "score": 2,
        "game_over": True,
        "end_reason": "deck_end",
        "hints_given": 0,
        "cards_played": 2,
        "cards_discarded": 1,
        "ply_count": 3,
        "moves_applied": [0, 1, 2],
        "moves_rejected": [3, 4, 5, 6],
        "fireworks": {"R": 1, "Y": 1, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s59_uneven_score": {
        "final_info_tokens": 6,
        "final_fuse_tokens": 3,
        "score": 13,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 3,
        "cards_discarded": 0,
        "ply_count": 3,
        "moves_applied": [0, 1, 2],
        "moves_rejected": [],
        "fireworks": {"R": 5, "Y": 2, "G": 0, "B": 4, "W": 2},
        "final_player": 1,
    },
    "s60_mixed_rejects_discard": {
        "final_info_tokens": 4,
        "final_fuse_tokens": 2,
        "score": 1,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 0,
        "cards_played": 0,
        "cards_discarded": 1,
        "ply_count": 1,
        "moves_applied": [3],
        "moves_rejected": [0, 1, 2],
        "fireworks": {"R": 1, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 1,
    },
    "s61_perfect_over_finale": {
        "final_info_tokens": 8,
        "final_fuse_tokens": 3,
        "score": 25,
        "game_over": True,
        "end_reason": "perfect",
        "hints_given": 0,
        "cards_played": 1,
        "cards_discarded": 1,
        "ply_count": 2,
        "moves_applied": [0, 1],
        "moves_rejected": [],
        "fireworks": {"R": 5, "Y": 5, "G": 5, "B": 5, "W": 5},
        "final_player": 1,
    },
    "s62_five_at_cap_then_hint": {
        "final_info_tokens": 7,
        "final_fuse_tokens": 3,
        "score": 5,
        "game_over": False,
        "end_reason": "none",
        "hints_given": 1,
        "cards_played": 1,
        "cards_discarded": 0,
        "ply_count": 2,
        "moves_applied": [0, 1],
        "moves_rejected": [],
        "fireworks": {"R": 5, "Y": 0, "G": 0, "B": 0, "W": 0},
        "final_player": 0,
    },
}


def load_json(path):
    """Load JSON document from path."""
    with open(path) as f:
        return json.load(f)


def sha256_file(path):
    """Hex digest of file bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def session_path(name):
    """Path to a scenario session_log.json."""
    return os.path.join(OUTPUT, name, "session_log.json")


def clone_fw(fw):
    """Copy firework map with all championship colors."""
    return {c: int(fw.get(c, 0)) for c in COLORS}


def score_sum(fw):
    """Championship score is the sum of firework heights."""
    return sum(fw[c] for c in COLORS)


def perfect(fw):
    """True when every color stack is complete."""
    return all(fw[c] == 5 for c in COLORS)


def simulate(sc):
    """Independently simulate a scenario under championship rules."""
    hands = [[dict(card) for card in hand] for hand in sc["hands"]]
    deck = [dict(card) for card in sc["deck"]]
    info = sc["info_tokens"]
    fuse = sc["fuse_tokens"]
    fw = clone_fw(sc["fireworks"])
    cur = sc["start_player"]
    players = sc["players"]
    game_over = False
    end_reason = "none"
    deck_was_empty = False
    final_left = 0
    applied, rejected = [], []
    hints = plays = discards = 0

    def draw():
        nonlocal deck, deck_was_empty, final_left
        if not deck:
            return None
        card = deck.pop(0)
        if not deck and not deck_was_empty:
            deck_was_empty = True
            final_left = players + 1
        return card

    def advance():
        nonlocal cur, final_left, game_over, end_reason
        if game_over:
            return
        cur = (cur + 1) % players
        if deck_was_empty:
            final_left -= 1
            if final_left <= 0:
                game_over = True
                if end_reason in ("", "none"):
                    end_reason = "deck_end"

    for i, mv in enumerate(sc["moves"]):
        if game_over:
            rejected.append(i)
            continue
        kind = mv["type"]
        if kind == "hint":
            to = mv["to"]
            if to < 0 or to >= players or to == cur or info < 1:
                rejected.append(i)
                continue
            hand = hands[to]
            matched = 0
            if mv["kind"] == "color":
                matched = sum(1 for card in hand if card["c"] == mv["value"])
            elif mv["kind"] == "rank":
                want = int(mv["value"])
                matched = sum(1 for card in hand if card["r"] == want)
            else:
                rejected.append(i)
                continue
            if matched == 0:
                rejected.append(i)
                continue
            info -= 1
            hints += 1
            applied.append(i)
            advance()
        elif kind == "play":
            idx = mv["index"]
            hand = hands[cur]
            if idx < 0 or idx >= len(hand):
                rejected.append(i)
                continue
            card = hand.pop(idx)
            expected = fw[card["c"]] + 1
            success = card["r"] == expected and expected <= 5
            if success:
                fw[card["c"]] = card["r"]
                if card["r"] == 5 and info < 8:
                    info += 1
                if perfect(fw):
                    game_over = True
                    end_reason = "perfect"
            else:
                fuse -= 1
                if fuse <= 0:
                    fuse = 0
                    game_over = True
                    end_reason = "fuse_out"
            if not game_over:
                drawn = draw()
                if drawn is not None:
                    hands[cur].append(drawn)
            plays += 1
            applied.append(i)
            advance()
        elif kind == "discard":
            idx = mv["index"]
            hand = hands[cur]
            if idx < 0 or idx >= len(hand):
                rejected.append(i)
                continue
            hand.pop(idx)
            if info < 8:
                info += 1
            drawn = draw()
            if drawn is not None:
                hands[cur].append(drawn)
            discards += 1
            applied.append(i)
            advance()
        else:
            rejected.append(i)

    return {
        "moves_applied": applied,
        "moves_rejected": rejected,
        "final_info_tokens": info,
        "final_fuse_tokens": fuse,
        "fireworks": fw,
        "score": score_sum(fw),
        "game_over": game_over,
        "end_reason": end_reason,
        "hints_given": hints,
        "cards_played": plays,
        "cards_discarded": discards,
        "ply_count": len(applied),
        "final_player": cur,
    }


class TestFixtureIntegrity:
    """Scenario and config fixtures must remain unmodified."""

    def test_scenario_checksums(self):
        """Each scenario JSON must match the pinned SHA-256 digest."""
        for name, digest in SCENARIO_SHA256.items():
            path = os.path.join(SCENARIOS, f"{name}.json")
            assert os.path.exists(path), f"missing scenario {path}"
            assert sha256_file(path) == digest, f"scenario tampered: {name}"

    def test_config_checksums(self):
        """Engine config and club table profile must match pinned digests."""
        for rel, digest in CONFIG_SHA256.items():
            path = os.path.join("/app", rel)
            assert os.path.exists(path), f"missing {path}"
            assert sha256_file(path) == digest, f"config tampered: {rel}"


class TestOutputPresence:
    """Required output files must exist for every scenario."""

    def test_all_session_logs_exist(self):
        """Every configured scenario must produce session_log.json."""
        for name in SCENARIO_SHA256:
            path = session_path(name)
            assert os.path.exists(path), f"missing {path}"

    def test_summary_exists(self):
        """Aggregate summary.json must exist."""
        assert os.path.exists(os.path.join(OUTPUT, "summary.json"))


class TestSessionSchema:
    """session_log.json must expose the championship schema."""

    REQUIRED: ClassVar[tuple[str, ...]] = (
        "scenario",
        "moves_applied",
        "moves_rejected",
        "final_info_tokens",
        "final_fuse_tokens",
        "fireworks",
        "score",
        "game_over",
        "end_reason",
        "hints_given",
        "cards_played",
        "cards_discarded",
        "ply_count",
        "final_player",
    )

    def test_keys_and_types(self):
        """Each session log has required keys with correct types."""
        for name in SCENARIO_SHA256:
            log = load_json(session_path(name))
            for key in self.REQUIRED:
                assert key in log, f"{name} missing {key}"
            assert isinstance(log["scenario"], str)
            assert isinstance(log["moves_applied"], list)
            assert isinstance(log["moves_rejected"], list)
            assert isinstance(log["final_info_tokens"], int)
            assert isinstance(log["final_fuse_tokens"], int)
            assert isinstance(log["fireworks"], dict)
            for color in COLORS:
                assert color in log["fireworks"]
                assert isinstance(log["fireworks"][color], int)
            assert isinstance(log["score"], int)
            assert isinstance(log["game_over"], bool)
            assert log["end_reason"] in ("none", "fuse_out", "perfect", "deck_end")
            assert isinstance(log["hints_given"], int)
            assert isinstance(log["cards_played"], int)
            assert isinstance(log["cards_discarded"], int)
            assert isinstance(log["ply_count"], int)
            assert isinstance(log["final_player"], int)


class TestConsistency:
    """Cross-field consistency for session logs."""

    def test_ply_count_matches_applied(self):
        """ply_count equals len(moves_applied)."""
        for name in SCENARIO_SHA256:
            log = load_json(session_path(name))
            assert log["ply_count"] == len(log["moves_applied"]), name

    def test_score_equals_firework_sum(self):
        """score equals the sum of firework heights."""
        for name in SCENARIO_SHA256:
            log = load_json(session_path(name))
            assert log["score"] == score_sum(log["fireworks"]), name


class TestIndependentSimulation:
    """Outputs must match an independent championship simulator."""

    def test_matches_reference_for_all_scenarios(self):
        """Each session log agrees with the independent reference engine."""
        for name in SCENARIO_SHA256:
            sc = load_json(os.path.join(SCENARIOS, f"{name}.json"))
            ref = simulate(sc)
            log = load_json(session_path(name))
            assert log["scenario"] == name
            for key in (
                "moves_applied",
                "moves_rejected",
                "final_info_tokens",
                "final_fuse_tokens",
                "fireworks",
                "score",
                "game_over",
                "end_reason",
                "hints_given",
                "cards_played",
                "cards_discarded",
                "ply_count",
                "final_player",
            ):
                assert log[key] == ref[key], f"{name}.{key}: {log[key]} != {ref[key]}"
            exp = EXPECTED[name]
            for key, value in exp.items():
                assert log[key] == value, f"{name}.{key}"


class TestSpecificRuleBehaviors:
    """Targeted checks for individual championship rule interactions."""

    def test_hint_costs_one_and_rotates(self):
        """s01 spends one info token and advances the player."""
        log = load_json(session_path("s01_simple_hint"))
        assert log["final_info_tokens"] == 7
        assert log["hints_given"] == 1
        assert log["final_player"] == 1

    def test_successful_play_no_fuse_loss(self):
        """s02 plays the next rank without consuming fuse tokens."""
        log = load_json(session_path("s02_play_success"))
        assert log["fireworks"]["R"] == 1
        assert log["final_fuse_tokens"] == 3
        assert log["score"] == 1

    def test_failed_play_consumes_fuse(self):
        """s03 reduces fuse on an illegal rank play."""
        log = load_json(session_path("s03_play_fail_fuse"))
        assert log["final_fuse_tokens"] == 2
        assert log["fireworks"]["R"] == 0

    def test_discard_restores_info(self):
        """s04 restores exactly one info token below the cap."""
        log = load_json(session_path("s04_discard_restore"))
        assert log["final_info_tokens"] == 7
        assert log["cards_discarded"] == 1

    def test_empty_hint_rejected(self):
        """s05 rejects an empty color hint then applies a legal hint."""
        log = load_json(session_path("s05_empty_hint_reject"))
        assert log["moves_rejected"] == [0]
        assert log["moves_applied"] == [1]
        assert log["final_info_tokens"] == 7

    def test_hint_requires_tokens(self):
        """s06 rejects a hint at zero info then allows a discard restore."""
        log = load_json(session_path("s06_hint_no_tokens"))
        assert log["moves_rejected"] == [0]
        assert log["moves_applied"] == [1]
        assert log["final_info_tokens"] == 1

    def test_five_restores_info(self):
        """s07 restores one info token when a five completes a stack."""
        log = load_json(session_path("s07_five_restores_info"))
        assert log["fireworks"]["R"] == 5
        assert log["final_info_tokens"] == 8
        assert log["final_fuse_tokens"] == 3

    def test_perfect_game_score_twenty_five(self):
        """s08 ends with perfect fireworks and score 25."""
        log = load_json(session_path("s08_perfect_game"))
        assert log["game_over"] is True
        assert log["end_reason"] == "perfect"
        assert log["score"] == 25
        assert log["final_fuse_tokens"] == 3

    def test_fuse_out_ends_match(self):
        """s09 ends when fuse tokens reach zero."""
        log = load_json(session_path("s09_fuse_out"))
        assert log["end_reason"] == "fuse_out"
        assert log["final_fuse_tokens"] == 0
        assert log["moves_rejected"] == [1]

    def test_illegal_then_legal(self):
        """s10 rejects illegal actions then applies a legal play."""
        log = load_json(session_path("s10_illegal_then_legal"))
        assert log["moves_rejected"] == [0, 1]
        assert log["moves_applied"] == [2]
        assert log["fireworks"]["R"] == 1

    def test_deck_end_final_round(self):
        """s11 ends with deck_end after the final-round counter expires."""
        log = load_json(session_path("s11_deck_end_final"))
        assert log["end_reason"] == "deck_end"
        assert log["game_over"] is True
        assert log["moves_rejected"] == [3]
        assert log["score"] == 2

    def test_discard_at_max_info_no_overflow(self):
        """s12 discards at max info without exceeding eight tokens."""
        log = load_json(session_path("s12_discard_at_max_info"))
        assert log["final_info_tokens"] == 8
        assert log["cards_discarded"] == 1


class TestSummary:
    """Aggregate summary must reflect per-scenario logs."""

    def test_summary_schema_and_totals(self):
        """summary.json counts and sums match the session logs."""
        summary = load_json(os.path.join(OUTPUT, "summary.json"))
        assert summary["scenario_count"] == len(SCENARIO_SHA256)
        for key in ("none", "fuse_out", "perfect", "deck_end"):
            assert key in summary["end_reasons"]
        logs = [load_json(session_path(n)) for n in SCENARIO_SHA256]
        assert summary["total_score"] == sum(entry["score"] for entry in logs)
        assert summary["total_hints"] == sum(entry["hints_given"] for entry in logs)
        assert summary["total_plays"] == sum(entry["cards_played"] for entry in logs)
        assert summary["total_discards"] == sum(entry["cards_discarded"] for entry in logs)
        assert summary["total_plies"] == sum(entry["ply_count"] for entry in logs)
        counts = Counter(entry["end_reason"] for entry in logs)
        for key in ("none", "fuse_out", "perfect", "deck_end"):
            assert summary["end_reasons"][key] == counts.get(key, 0)


class TestExtendedRuleBehaviors:
    """Additional championship edge cases across new and existing scenarios."""

    def test_self_hint_rejected_then_rank_hint(self):
        """s13 rejects a self-hint then applies a legal rank hint."""
        log = load_json(session_path("s13_self_hint_reject"))
        assert log["moves_rejected"] == [0]
        assert log["moves_applied"] == [1]
        assert log["hints_given"] == 1
        assert log["final_info_tokens"] == 7

    def test_self_hint_preserves_turn_until_legal(self):
        """s13 keeps ownership until the legal hint rotates it."""
        log = load_json(session_path("s13_self_hint_reject"))
        assert log["final_player"] == 1
        assert log["ply_count"] == 1

    def test_rank_hint_costs_one_token(self):
        """s14 spends exactly one information token on a rank hint."""
        log = load_json(session_path("s14_rank_hint_rotate"))
        assert log["final_info_tokens"] == 4
        assert log["hints_given"] == 1
        assert log["score"] == 1

    def test_rank_hint_rotates_player(self):
        """s14 advances turn ownership after a legal rank hint."""
        log = load_json(session_path("s14_rank_hint_rotate"))
        assert log["final_player"] == 1
        assert log["moves_applied"] == [0]

    def test_skip_ahead_does_not_raise_stack(self):
        """s15 refuses skip-ahead placement and leaves the stack unchanged."""
        log = load_json(session_path("s15_skip_ahead_fail"))
        assert log["fireworks"]["R"] == 1
        assert log["score"] == 1

    def test_skip_ahead_consumes_fuse(self):
        """s15 decrements fuse tokens on a skip-ahead failure."""
        log = load_json(session_path("s15_skip_ahead_fail"))
        assert log["final_fuse_tokens"] == 2
        assert log["cards_played"] == 1
        assert log["game_over"] is False

    def test_five_at_max_info_no_overflow(self):
        """s16 completes a five at max info without exceeding eight tokens."""
        log = load_json(session_path("s16_five_at_max_info"))
        assert log["fireworks"]["R"] == 5
        assert log["final_info_tokens"] == 8
        assert log["score"] == 5

    def test_five_at_max_info_no_fuse_loss(self):
        """s16 successful five play does not consume fuse tokens."""
        log = load_json(session_path("s16_five_at_max_info"))
        assert log["final_fuse_tokens"] == 3
        assert log["end_reason"] == "none"

    def test_hint_play_chain_scores_two(self):
        """s17 chains hint then two plays to score two firework ranks."""
        log = load_json(session_path("s17_hint_play_chain"))
        assert log["score"] == 2
        assert log["fireworks"]["R"] == 1
        assert log["fireworks"]["Y"] == 1

    def test_hint_play_chain_token_and_plies(self):
        """s17 records one hint, two plays, and three applied plies."""
        log = load_json(session_path("s17_hint_play_chain"))
        assert log["hints_given"] == 1
        assert log["cards_played"] == 2
        assert log["ply_count"] == 3
        assert log["final_info_tokens"] == 3

    def test_perfect_preserves_acting_player(self):
        """s18 keeps final_player on the actor who completed the perfect game."""
        log = load_json(session_path("s18_perfect_mid_ownership"))
        assert log["end_reason"] == "perfect"
        assert log["final_player"] == 2
        assert log["score"] == 25

    def test_perfect_restores_info_on_final_five(self):
        """s18 restores one info token when the completing five is below the ceiling."""
        log = load_json(session_path("s18_perfect_mid_ownership"))
        assert log["final_info_tokens"] == 8
        assert log["final_fuse_tokens"] == 3
        assert log["game_over"] is True

    def test_deck_end_three_player_counter(self):
        """s19 ends with deck_end under a three-player final-round counter."""
        log = load_json(session_path("s19_deck_end_three"))
        assert log["end_reason"] == "deck_end"
        assert log["game_over"] is True
        assert log["moves_rejected"] == [4]

    def test_deck_end_three_score_and_player(self):
        """s19 scores three and leaves ownership on the ending advance actor."""
        log = load_json(session_path("s19_deck_end_three"))
        assert log["score"] == 3
        assert log["final_player"] == 1
        assert log["cards_played"] == 3
        assert log["cards_discarded"] == 1

    def test_fuse_out_priority_over_deck_end(self):
        """s20 reports fuse_out even after the deck has emptied."""
        log = load_json(session_path("s20_fuse_beats_deck"))
        assert log["end_reason"] == "fuse_out"
        assert log["final_fuse_tokens"] == 0
        assert log["game_over"] is True

    def test_fuse_out_preserves_failing_player(self):
        """s20 keeps final_player on the player whose failed play emptied the fuse."""
        log = load_json(session_path("s20_fuse_beats_deck"))
        assert log["final_player"] == 1
        assert log["score"] == 1
        assert log["cards_played"] == 2

    def test_double_discard_restores_to_ceiling(self):
        """s21 restores one token per discard until the information ceiling."""
        log = load_json(session_path("s21_double_discard"))
        assert log["final_info_tokens"] == 8
        assert log["cards_discarded"] == 2
        assert log["score"] == 3

    def test_double_discard_full_rotation(self):
        """s21 returns ownership to the start player after two legal discards."""
        log = load_json(session_path("s21_double_discard"))
        assert log["final_player"] == 0
        assert log["ply_count"] == 2
        assert log["moves_rejected"] == []

    def test_empty_rank_hint_rejected(self):
        """s22 rejects an empty rank hint then applies a legal color hint."""
        log = load_json(session_path("s22_empty_rank_hint"))
        assert log["moves_rejected"] == [0]
        assert log["moves_applied"] == [1]
        assert log["final_info_tokens"] == 6

    def test_empty_rank_hint_no_side_effects(self):
        """s22 leaves fireworks and fuse unchanged after the empty rank reject."""
        log = load_json(session_path("s22_empty_rank_hint"))
        assert log["score"] == 0
        assert log["final_fuse_tokens"] == 3
        assert log["hints_given"] == 1

    def test_invalid_hint_targets_rejected(self):
        """s23 rejects out-of-range hint targets then applies a discard."""
        log = load_json(session_path("s23_invalid_hint_target"))
        assert log["moves_rejected"] == [0, 1]
        assert log["moves_applied"] == [2]
        assert log["cards_discarded"] == 1

    def test_invalid_hint_targets_preserve_info(self):
        """s23 does not spend information tokens on invalid hint targets."""
        log = load_json(session_path("s23_invalid_hint_target"))
        assert log["final_info_tokens"] == 8
        assert log["hints_given"] == 0
        assert log["final_player"] == 1

    def test_zero_info_rejects_hints(self):
        """s24 rejects hints at zero information before a discard restore."""
        log = load_json(session_path("s24_zero_info_multi"))
        assert log["moves_rejected"] == [0, 1]
        assert log["moves_applied"] == [2, 3]
        assert log["final_info_tokens"] == 1

    def test_zero_info_then_play_after_discard(self):
        """s24 discards to restore info then plays successfully on the next turn."""
        log = load_json(session_path("s24_zero_info_multi"))
        assert log["cards_discarded"] == 1
        assert log["cards_played"] == 1
        assert log["fireworks"]["Y"] == 1
        assert log["score"] == 2

    def test_perfect_game_final_player_zero(self):
        """s08 ending perfect play leaves final_player on the completing actor."""
        log = load_json(session_path("s08_perfect_game"))
        assert log["final_player"] == 0
        assert log["end_reason"] == "perfect"
        assert log["game_over"] is True

    def test_fuse_out_final_player_zero(self):
        """s09 ending fuse-out play leaves final_player on the failing actor."""
        log = load_json(session_path("s09_fuse_out"))
        assert log["final_player"] == 0
        assert log["end_reason"] == "fuse_out"
        assert log["moves_rejected"] == [1]

    def test_deck_end_rejects_after_close(self):
        """s11 rejects trailing moves once the final-round counter expires."""
        log = load_json(session_path("s11_deck_end_final"))
        assert log["moves_rejected"] == [3]
        assert log["end_reason"] == "deck_end"
        assert log["final_player"] == 1

    def test_summary_perfect_and_fuse_counts(self):
        """summary end_reasons include both perfect completions and fuse-outs."""
        summary = load_json(os.path.join(OUTPUT, "summary.json"))
        assert summary["end_reasons"]["perfect"] >= 2
        assert summary["end_reasons"]["fuse_out"] >= 2
        assert summary["end_reasons"]["deck_end"] >= 2

    def test_summary_scenario_count_twenty_four(self):
        """summary scenario_count matches the full configured scenario suite."""
        summary = load_json(os.path.join(OUTPUT, "summary.json"))
        assert summary["scenario_count"] == len(SCENARIO_SHA256)
        assert summary["total_plies"] > 0

    def test_all_fireworks_keys_present_extended(self):
        """Every extended scenario session log exposes all five firework colors."""
        for name in (
            "s13_self_hint_reject",
            "s18_perfect_mid_ownership",
            "s19_deck_end_three",
            "s24_zero_info_multi",
        ):
            log = load_json(session_path(name))
            for color in COLORS:
                assert color in log["fireworks"]
                assert isinstance(log["fireworks"][color], int)


class TestAdditionalChampionshipCases:
    """Thirty additional championship edge-case assertions on the expanded suite."""

    def test_s25_deck_end_reason(self):
        """s25 ends with deck_end after the wrapped final-round counter expires."""
        log = load_json(session_path("s25_deck_end_wrap"))
        assert log["end_reason"] == "deck_end"
        assert log["game_over"] is True

    def test_s25_final_player_after_rotation(self):
        """s25 records final_player after the deck_end advance rotation (seat 0)."""
        log = load_json(session_path("s25_deck_end_wrap"))
        assert log["final_player"] == 0
        assert log["moves_rejected"] == [4, 5]

    def test_s25_score_and_plies(self):
        """s25 scores two from successful plays across four applied plies."""
        log = load_json(session_path("s25_deck_end_wrap"))
        assert log["score"] == 2
        assert log["ply_count"] == 4
        assert log["cards_played"] == 2
        assert log["cards_discarded"] == 2

    def test_s25_fireworks_partial(self):
        """s25 leaves only red and yellow stacks raised."""
        log = load_json(session_path("s25_deck_end_wrap"))
        assert log["fireworks"]["R"] == 1
        assert log["fireworks"]["Y"] == 1
        assert log["fireworks"]["G"] == 0

    def test_s26_four_player_deck_end(self):
        """s26 ends with deck_end under a four-player final-round counter."""
        log = load_json(session_path("s26_deck_end_four"))
        assert log["end_reason"] == "deck_end"
        assert log["game_over"] is True
        assert log["ply_count"] == 5

    def test_s26_final_player_one(self):
        """s26 leaves final_player on seat 1 after the closing advance rotation."""
        log = load_json(session_path("s26_deck_end_four"))
        assert log["final_player"] == 1
        assert log["moves_rejected"] == [5]

    def test_s26_four_color_score(self):
        """s26 scores four with one rank on each of four colors."""
        log = load_json(session_path("s26_deck_end_four"))
        assert log["score"] == 4
        assert log["cards_played"] == 4
        assert log["fireworks"]["B"] == 1

    def test_s26_info_after_discard(self):
        """s26 restores one information token on the closing discard."""
        log = load_json(session_path("s26_deck_end_four"))
        assert log["final_info_tokens"] == 7
        assert log["cards_discarded"] == 1

    def test_s27_perfect_priority(self):
        """s27 reports perfect even though the deck emptied earlier."""
        log = load_json(session_path("s27_perfect_beats_deck"))
        assert log["end_reason"] == "perfect"
        assert log["score"] == 25
        assert log["game_over"] is True

    def test_s27_acting_player_preserved(self):
        """s27 keeps final_player on the actor who completed the perfect game."""
        log = load_json(session_path("s27_perfect_beats_deck"))
        assert log["final_player"] == 0
        assert log["cards_played"] == 1

    def test_s27_info_restored_on_five(self):
        """s27 restores information when the completing five is below the ceiling."""
        log = load_json(session_path("s27_perfect_beats_deck"))
        assert log["final_info_tokens"] == 8
        assert log["final_fuse_tokens"] == 3

    def test_s27_discards_before_perfect(self):
        """s27 applies two discards before the perfect-completing play."""
        log = load_json(session_path("s27_perfect_beats_deck"))
        assert log["cards_discarded"] == 2
        assert log["moves_applied"] == [0, 1, 2]
        assert log["moves_rejected"] == []

    def test_s28_hint_then_fail_fuse(self):
        """s28 spends a hint then loses a fuse on a skip-ahead failure."""
        log = load_json(session_path("s28_hint_fail_discard"))
        assert log["hints_given"] == 1
        assert log["final_fuse_tokens"] == 2
        assert log["end_reason"] == "none"

    def test_s28_discard_restores_after_fail(self):
        """s28 restores information after the failed play via discard."""
        log = load_json(session_path("s28_hint_fail_discard"))
        assert log["final_info_tokens"] == 3
        assert log["cards_discarded"] == 1
        assert log["cards_played"] == 2

    def test_s28_partial_score(self):
        """s28 scores two from red and yellow stacks after the chain."""
        log = load_json(session_path("s28_hint_fail_discard"))
        assert log["score"] == 2
        assert log["fireworks"]["R"] == 1
        assert log["fireworks"]["Y"] == 1

    def test_s28_full_rotation(self):
        """s28 returns ownership to seat 0 after four legal actions."""
        log = load_json(session_path("s28_hint_fail_discard"))
        assert log["final_player"] == 0
        assert log["ply_count"] == 4
        assert log["moves_rejected"] == []

    def test_s29_rejects_four_illegal_hints(self):
        """s29 rejects four illegal hints before one legal color hint."""
        log = load_json(session_path("s29_multi_reject_hint"))
        assert log["moves_rejected"] == [0, 1, 2, 3]
        assert log["moves_applied"] == [4]
        assert log["hints_given"] == 1

    def test_s29_info_spent_once(self):
        """s29 spends exactly one information token on the legal hint."""
        log = load_json(session_path("s29_multi_reject_hint"))
        assert log["final_info_tokens"] == 7
        assert log["final_fuse_tokens"] == 3
        assert log["score"] == 0

    def test_s29_rotates_after_legal_only(self):
        """s29 advances ownership only after the accepted hint."""
        log = load_json(session_path("s29_multi_reject_hint"))
        assert log["final_player"] == 1
        assert log["ply_count"] == 1
        assert log["game_over"] is False

    def test_s30_fuse_out_not_deck_end(self):
        """s30 reports fuse_out during an armed finale instead of deck_end."""
        log = load_json(session_path("s30_fuse_during_finale"))
        assert log["end_reason"] == "fuse_out"
        assert log["final_fuse_tokens"] == 0
        assert log["game_over"] is True

    def test_s30_failing_player_preserved(self):
        """s30 keeps final_player on the seat whose failed play emptied the fuse."""
        log = load_json(session_path("s30_fuse_during_finale"))
        assert log["final_player"] == 1
        assert log["moves_rejected"] == [2]

    def test_s30_score_one_before_fuse_out(self):
        """s30 keeps the successful first play score of one."""
        log = load_json(session_path("s30_fuse_during_finale"))
        assert log["score"] == 1
        assert log["fireworks"]["R"] == 1
        assert log["cards_played"] == 2

    def test_s31_five_then_hint_then_discard_cap(self):
        """s31 completes a five, spends a hint, then discards back to the ceiling."""
        log = load_json(session_path("s31_five_hint_discard_cap"))
        assert log["fireworks"]["R"] == 5
        assert log["final_info_tokens"] == 8
        assert log["hints_given"] == 1
        assert log["cards_discarded"] == 1

    def test_s31_no_fuse_loss_on_success(self):
        """s31 successful five play does not consume fuse tokens."""
        log = load_json(session_path("s31_five_hint_discard_cap"))
        assert log["final_fuse_tokens"] == 3
        assert log["end_reason"] == "none"
        assert log["score"] == 5

    def test_s31_rotation_after_three_plies(self):
        """s31 ends on seat 1 after three legal actions from seat 0."""
        log = load_json(session_path("s31_five_hint_discard_cap"))
        assert log["final_player"] == 1
        assert log["ply_count"] == 3
        assert log["moves_applied"] == [0, 1, 2]

    def test_s32_rejects_bad_indices(self):
        """s32 rejects out-of-range play indices then applies a legal play."""
        log = load_json(session_path("s32_bad_play_index"))
        assert log["moves_rejected"] == [0, 1]
        assert log["moves_applied"] == [2]
        assert log["fireworks"]["R"] == 1

    def test_s32_no_fuse_on_rejects(self):
        """s32 does not consume fuse tokens on rejected out-of-range plays."""
        log = load_json(session_path("s32_bad_play_index"))
        assert log["final_fuse_tokens"] == 3
        assert log["cards_played"] == 1
        assert log["score"] == 1

    def test_s32_rotates_after_legal_play(self):
        """s32 advances ownership only after the accepted play."""
        log = load_json(session_path("s32_bad_play_index"))
        assert log["final_player"] == 1
        assert log["ply_count"] == 1
        assert log["end_reason"] == "none"

    def test_summary_includes_new_deck_ends(self):
        """summary counts at least four deck_end finishes across the expanded suite."""
        summary = load_json(os.path.join(OUTPUT, "summary.json"))
        assert summary["end_reasons"]["deck_end"] >= 4
        assert summary["end_reasons"]["perfect"] >= 3
        assert summary["end_reasons"]["fuse_out"] >= 3

    def test_summary_scenario_count_thirty_two(self):
        """summary scenario_count matches the full configured scenario suite."""
        summary = load_json(os.path.join(OUTPUT, "summary.json"))
        assert summary["scenario_count"] == len(SCENARIO_SHA256)
        assert summary["total_score"] > 0


class TestHardChampionshipSuite:
    """Thirty additional hard edge-case scenarios (s33-s62)."""

    def test_s33_empty_deck_perfect_mid(self):
        """empty deck at start still ends perfect."""
        log = load_json(session_path("s33_empty_deck_perfect_mid"))
        assert log["end_reason"] == "perfect"
        assert log["score"] == 25
        assert log["final_player"] == 1

    def test_s34_empty_deck_fuse_priority(self):
        """empty deck fuse_out beats any deck_end."""
        log = load_json(session_path("s34_empty_deck_fuse_priority"))
        assert log["end_reason"] == "fuse_out"
        assert log["final_fuse_tokens"] == 0
        assert log["final_player"] == 0

    def test_s35_draw_then_perfect(self):
        """perfect after emptying draw beats deck_end."""
        log = load_json(session_path("s35_draw_then_perfect"))
        assert log["end_reason"] == "perfect"
        assert log["score"] == 25
        assert log["ply_count"] == 2

    def test_s36_draw_then_fuse(self):
        """fuse_out after emptying draw beats deck_end."""
        log = load_json(session_path("s36_draw_then_fuse"))
        assert log["end_reason"] == "fuse_out"
        assert log["score"] == 2
        assert log["final_player"] == 1

    def test_s37_hint_during_finale(self):
        """legal hint during finale then deck_end."""
        log = load_json(session_path("s37_hint_during_finale"))
        assert log["end_reason"] == "deck_end"
        assert log["hints_given"] == 1
        assert log["moves_rejected"] == [3, 4]

    def test_s38_max_info_finale_discard(self):
        """discard at info ceiling during finale."""
        log = load_json(session_path("s38_max_info_finale_discard"))
        assert log["end_reason"] == "deck_end"
        assert log["final_info_tokens"] == 8
        assert log["score"] == 2

    def test_s39_five_then_ceiling(self):
        """five restore then discard and hint under ceiling."""
        log = load_json(session_path("s39_five_then_ceiling"))
        assert log["score"] == 5
        assert log["final_info_tokens"] == 7
        assert log["hints_given"] == 1

    def test_s40_rejects_then_fuse_out(self):
        """rejects then fuse_out on illegal play."""
        log = load_json(session_path("s40_rejects_then_fuse_out"))
        assert log["end_reason"] == "fuse_out"
        assert log["moves_applied"] == [3]
        assert log["moves_rejected"] == [0, 1, 2, 4]

    def test_s41_hint_reject_cascade(self):
        """cascade of illegal hints then one legal rank hint."""
        log = load_json(session_path("s41_hint_reject_cascade"))
        assert log["moves_applied"] == [4]
        assert log["moves_rejected"] == [0, 1, 2, 3]
        assert log["final_info_tokens"] == 4

    def test_s42_skip_two_ranks(self):
        """skip-ahead by two ranks fails then legal play."""
        log = load_json(session_path("s42_skip_two_ranks"))
        assert log["final_fuse_tokens"] == 2
        assert log["score"] == 2
        assert log["fireworks"]["R"] == 2

    def test_s43_double_five_restore(self):
        """two consecutive fives restore info toward ceiling."""
        log = load_json(session_path("s43_double_five_restore"))
        assert log["score"] == 10
        assert log["final_info_tokens"] == 8
        assert log["cards_played"] == 2

    def test_s44_three_deck_start2(self):
        """three-player deck_end from start_player 2."""
        log = load_json(session_path("s44_three_deck_start2"))
        assert log["end_reason"] == "deck_end"
        assert log["final_player"] == 0
        assert log["score"] == 3

    def test_s45_four_fuse_finale(self):
        """four-player fuse_out mid-finale preserves seat."""
        log = load_json(session_path("s45_four_fuse_finale"))
        assert log["end_reason"] == "fuse_out"
        assert log["final_player"] == 3
        assert log["score"] == 3

    def test_s46_index_shift_play(self):
        """hand index shift after discards then play."""
        log = load_json(session_path("s46_index_shift_play"))
        assert log["score"] == 1
        assert log["cards_discarded"] == 2
        assert log["cards_played"] == 1

    def test_s47_perfect_start1(self):
        """perfect with start_player 1 preserves actor."""
        log = load_json(session_path("s47_perfect_start1"))
        assert log["end_reason"] == "perfect"
        assert log["final_player"] == 1
        assert log["score"] == 25

    def test_s48_single_fuse_fail(self):
        """single fuse token empties on first failed play."""
        log = load_json(session_path("s48_single_fuse_fail"))
        assert log["end_reason"] == "fuse_out"
        assert log["final_fuse_tokens"] == 0
        assert log["final_player"] == 0

    def test_s49_zero_info_chain(self):
        """zero info rejects hints then discard-hint-play."""
        log = load_json(session_path("s49_zero_info_chain"))
        assert log["moves_rejected"] == [0, 1]
        assert log["score"] == 1
        assert log["final_info_tokens"] == 0

    def test_s50_duplicate_rank_fail(self):
        """duplicate stack rank fails then next rank succeeds."""
        log = load_json(session_path("s50_duplicate_rank_fail"))
        assert log["final_fuse_tokens"] == 2
        assert log["score"] == 3
        assert log["fireworks"]["R"] == 3

    def test_s51_one_card_exact_finale(self):
        """one-card deck exact finale length."""
        log = load_json(session_path("s51_one_card_exact_finale"))
        assert log["end_reason"] == "deck_end"
        assert log["ply_count"] == 3
        assert log["moves_rejected"] == [3, 4]

    def test_s52_invalid_hint_kind(self):
        """invalid hint kind rejected then legal color hint."""
        log = load_json(session_path("s52_invalid_hint_kind"))
        assert log["moves_rejected"] == [0]
        assert log["moves_applied"] == [1]
        assert log["hints_given"] == 1

    def test_s53_neg_discard_then_play(self):
        """negative and OOR discard rejected then play."""
        log = load_json(session_path("s53_neg_discard_then_play"))
        assert log["moves_rejected"] == [0, 1]
        assert log["moves_applied"] == [2]
        assert log["score"] == 1

    def test_s54_play_drawn_card(self):
        """play previously drawn card after rotation."""
        log = load_json(session_path("s54_play_drawn_card"))
        assert log["score"] == 1
        assert log["cards_discarded"] == 2
        assert log["cards_played"] == 1

    def test_s55_fuse_chain_zero(self):
        """three failed plays drain fuse across seats."""
        log = load_json(session_path("s55_fuse_chain_zero"))
        assert log["end_reason"] == "fuse_out"
        assert log["final_player"] == 2
        assert log["score"] == 0

    def test_s56_empty_multi_perfect(self):
        """empty-deck multi-play perfect completes all stacks."""
        log = load_json(session_path("s56_empty_multi_perfect"))
        assert log["end_reason"] == "perfect"
        assert log["score"] == 25
        assert log["final_player"] == 0

    def test_s57_illegal_no_finale_tick(self):
        """illegal actions during finale do not end early."""
        log = load_json(session_path("s57_illegal_no_finale_tick"))
        assert log["end_reason"] == "deck_end"
        assert log["moves_rejected"] == [1, 2, 5, 6]
        assert log["score"] == 2

    def test_s58_trailing_after_deck_end(self):
        """trailing moves rejected after deck_end."""
        log = load_json(session_path("s58_trailing_after_deck_end"))
        assert log["end_reason"] == "deck_end"
        assert log["moves_rejected"] == [3, 4, 5, 6]
        assert log["score"] == 2

    def test_s59_uneven_score(self):
        """uneven firework heights sum to championship score."""
        log = load_json(session_path("s59_uneven_score"))
        assert log["score"] == 13
        assert log["fireworks"]["R"] == 5
        assert log["fireworks"]["Y"] == 2
        assert log["fireworks"]["G"] == 0
        assert log["fireworks"]["B"] == 4
        assert log["fireworks"]["W"] == 2

    def test_s60_mixed_rejects_discard(self):
        """mixed illegal actions then legal discard."""
        log = load_json(session_path("s60_mixed_rejects_discard"))
        assert log["moves_applied"] == [3]
        assert log["moves_rejected"] == [0, 1, 2]
        assert log["cards_discarded"] == 1

    def test_s61_perfect_over_finale(self):
        """perfect after arming finale beats deck_end."""
        log = load_json(session_path("s61_perfect_over_finale"))
        assert log["end_reason"] == "perfect"
        assert log["score"] == 25
        assert log["final_player"] == 1

    def test_s62_five_at_cap_then_hint(self):
        """five at info cap then hint spends one token."""
        log = load_json(session_path("s62_five_at_cap_then_hint"))
        assert log["score"] == 5
        assert log["final_info_tokens"] == 7
        assert log["hints_given"] == 1

    def test_summary_scenario_count_sixty_two(self):
        """summary scenario_count matches the sixty-two scenario suite."""
        summary = load_json(os.path.join(OUTPUT, "summary.json"))
        assert summary["scenario_count"] == 62
        assert summary["total_score"] > 0

    def test_summary_expanded_end_reason_floors(self):
        """expanded suite includes multiple perfect, fuse_out, and deck_end finishes."""
        summary = load_json(os.path.join(OUTPUT, "summary.json"))
        assert summary["end_reasons"]["perfect"] >= 8
        assert summary["end_reasons"]["fuse_out"] >= 9
        assert summary["end_reasons"]["deck_end"] >= 10

