"""Mock evidence cards for the /dashboard demo. Not real riders or orders."""

MOCK_DISPUTES = [
    {
        "card": {
            "order_id": "ZMT-482913", "rider_id": "R-1042", "otp_confirmed": True, "gps_matched": True,
            "delivery_status": "delivered", "handover_location": "door", "obstacle": "none",
            "customer_instruction": "not_mentioned", "confidence": "high",
            "spoken_context": "Handed to the customer at the door, he gave the OTP, photo taken.",
        },
        "transcript": "Customer ko door pe diya, OTP diya usne, photo le li.",
        "customer_claim": "Order not delivered",
        "timestamp": "2026-11-26T13:42:10Z",
    },
    {
        "card": {
            "order_id": "SWG-771204", "rider_id": "R-2217", "otp_confirmed": True, "gps_matched": True,
            "delivery_status": "delivered", "handover_location": "security", "obstacle": "customer_unavailable",
            "customer_instruction": "not_mentioned", "confidence": "high",
            "spoken_context": "Customer's phone was off, handed the package to the watchman at the gate.",
        },
        "transcript": "Customer ka phone बंद था, watchman को gate पे दे दिया.",
        "customer_claim": "Never received my order",
        "timestamp": "2026-11-26T19:05:44Z",
    },
    {
        "card": {
            "order_id": "ZPT-330981", "rider_id": "R-0583", "otp_confirmed": False, "gps_matched": True,
            "delivery_status": "delivered", "handover_location": "neighbor", "obstacle": "customer_unavailable",
            "customer_instruction": "not_mentioned", "confidence": "medium",
            "spoken_context": "Nobody answered, left it with the neighbour next door.",
        },
        "transcript": "Koi nahi khola, bagal wale neighbour ko de diya.",
        "customer_claim": "Not delivered",
        "timestamp": "2026-11-27T08:21:03Z",
    },
    {
        "card": {
            "order_id": "BLK-905516", "rider_id": "R-1188", "otp_confirmed": True, "gps_matched": True,
            "delivery_status": "delivered", "handover_location": "reception", "obstacle": "gate_locked",
            "customer_instruction": "leave at reception", "confidence": "high",
            "spoken_context": "Third floor gate was locked, customer said to leave it at reception, photo taken.",
        },
        "transcript": "Teen floor, gate locked tha, customer ne bola reception pe chhod do, photo liya.",
        "customer_claim": "Wrong item delivered",
        "timestamp": "2026-11-27T10:14:37Z",
    },
    {
        "card": {
            "order_id": "AMZ-118274", "rider_id": "R-3051", "otp_confirmed": True, "gps_matched": False,
            "delivery_status": "delivered", "handover_location": "not_mentioned", "obstacle": "not_mentioned",
            "customer_instruction": "not_mentioned", "confidence": "low",
            "spoken_context": "Yes, it's done.",
        },
        "transcript": "हां बस हो गया.",
        "customer_claim": "Package not received",
        "timestamp": "2026-11-27T11:52:19Z",
    },
]
