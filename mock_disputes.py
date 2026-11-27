"""Mock evidence cards for the /dashboard demo. Not real riders or orders."""


def _card(order_id, rider_id, otp, gps, status, location, obstacle, confidence, context, instruction="not_mentioned"):
    return {
        "order_id": order_id, "rider_id": rider_id, "otp_confirmed": otp, "gps_matched": gps,
        "delivery_status": status, "handover_location": location, "obstacle": obstacle,
        "customer_instruction": instruction, "confidence": confidence, "spoken_context": context,
    }


MOCK_DISPUTES = [
    {
        "card": _card("ZMT-482913", "R-1042", True, True, "delivered", "door", "none", "high",
                      "Handed to the customer at the door, he gave the OTP, photo taken."),
        "transcript": "Customer ko door pe diya, OTP diya usne, photo le li.",
        "customer_claim": "Order not delivered",
        "timestamp": "2026-11-27T08:12:10Z",
    },
    {
        "card": _card("SWG-771204", "R-2217", True, True, "delivered", "security", "customer_unavailable", "high",
                      "Customer's phone was off, handed the package to the watchman at the gate."),
        "transcript": "Customer ka phone बंद था, watchman को gate पे दे दिया.",
        "customer_claim": "Never received my order",
        "timestamp": "2026-11-27T07:55:44Z",
    },
    {
        "card": _card("BLK-905516", "R-1188", True, True, "delivered", "reception", "gate_locked", "high",
                      "Third floor gate was locked, customer said to leave it at reception, photo taken.",
                      "leave at reception"),
        "transcript": "Teen floor, gate locked tha, customer ne bola reception pe chhod do, photo liya.",
        "customer_claim": "Wrong item delivered",
        "timestamp": "2026-11-27T07:41:37Z",
    },
    {
        "card": _card("ZPT-330981", "R-0583", False, True, "delivered", "neighbor", "customer_unavailable", "medium",
                      "Nobody answered, left it with the neighbour next door."),
        "transcript": "Koi nahi khola, bagal wale neighbour ko de diya.",
        "customer_claim": "Not delivered",
        "timestamp": "2026-11-27T07:21:03Z",
    },
    {
        "card": _card("ZMT-559102", "R-0907", True, True, "delivered", "door", "none", "high",
                      "Gave it to the customer's mother at the door, she shared the OTP."),
        "transcript": "Customer ki mummy ko door pe diya, unhone OTP bataya.",
        "customer_claim": "Order never arrived",
        "timestamp": "2026-11-27T06:58:51Z",
    },
    {
        "card": _card("AMZ-118274", "R-3051", True, False, "delivered", "not_mentioned", "not_mentioned", "low",
                      "Yes, it's done."),
        "transcript": "हां बस हो गया.",
        "customer_claim": "Package not received",
        "timestamp": "2026-11-27T06:52:19Z",
    },
    {
        "card": _card("ZPT-884210", "R-2217", True, False, "delivered", "neighbor", "customer_unavailable", "high",
                      "Customer not home, handed it to the neighbour in flat 402 as the customer asked on call.",
                      "give to neighbour in 402"),
        "transcript": "Customer ghar pe nahi tha, call pe bola 402 wale neighbour ko de do, de diya.",
        "customer_claim": "Not delivered",
        "timestamp": "2026-11-27T06:30:12Z",
    },
    {
        "card": _card("SWG-640338", "R-1420", True, True, "delivered", "reception", "customer_unavailable", "medium",
                      "Customer didn't pick up, left it at the office reception."),
        "transcript": "Customer phone nahi utha raha tha, office reception pe chhod diya.",
        "customer_claim": "Not delivered",
        "timestamp": "2026-11-27T06:04:48Z",
    },
    {
        "card": _card("AMZ-402998", "R-3051", True, True, "partial", "door", "none", "high",
                      "Handed one of two packets at the door, the second one comes tomorrow."),
        "transcript": "Do mein se ek packet door pe diya, doosra kal aayega.",
        "customer_claim": "Items missing from order",
        "timestamp": "2026-11-27T05:47:26Z",
    },
    {
        "card": _card("BLK-217745", "R-0583", False, False, "not_mentioned", "not_mentioned", "not_mentioned", "low",
                      "Unclear audio: rider mentions a drop but no place or person."),
        "transcript": "Haan... drop... kiya.",
        "customer_claim": "Not delivered",
        "timestamp": "2026-11-27T05:20:09Z",
    },
]
