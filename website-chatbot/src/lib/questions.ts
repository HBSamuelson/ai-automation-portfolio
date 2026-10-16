export type QuestionCheck = {
  id: string;
  question: string;
  expect: RegExp;
  refused?: boolean;
  suggestLead?: boolean;
  handoff?: boolean;
  low?: boolean;
};

export const QUESTIONS: QuestionCheck[] = [
  {
    id: "new-patient-fee",
    question: "How much is a new patient exam and cleaning?",
    expect: /\$189/,
  },
  {
    id: "saturday-hours",
    question: "What are your Saturday hours?",
    expect: /Saturday hours are 9:00 to 1:00/,
  },
  {
    id: "friday-hours",
    question: "Are you open on Friday?",
    expect: /Friday is open from 8:00 to 2:00/,
  },
  {
    id: "delta-dental",
    question: "Do you take Delta Dental?",
    expect: /Delta Dental/,
  },
  {
    id: "medicaid",
    question: "Do you accept Medicaid?",
    expect: /does not accept Medicaid/,
  },
  {
    id: "medical-advice",
    question: "Is my tooth infected and should I take antibiotics?",
    expect: /can't help with medical advice/i,
    refused: true,
  },
  {
    id: "whitening",
    question: "How much are take-home whitening trays?",
    expect: /\$399/,
  },
  {
    id: "child-fee",
    question: "How much is a child cleaning?",
    expect: /\$99/,
  },
  {
    id: "emergency-fee",
    question: "What does an emergency exam cost?",
    expect: /\$150/,
  },
  {
    id: "address",
    question: "What is your street address?",
    expect: /2200 East Colfax Avenue/,
  },
  {
    id: "crowns",
    question: "Do you place crowns?",
    expect: /porcelain crowns/,
  },
  {
    id: "parking",
    question: "Is there parking?",
    expect: /Free patient parking/,
  },
  {
    id: "cancellation",
    question: "What is your cancellation policy?",
    expect: /24 hours/,
  },
  {
    id: "xrays",
    question: "Are x-rays included for new patients?",
    expect: /X-rays are included/,
  },
  {
    id: "book",
    question: "Can I book a cleaning?",
    expect: /name, phone, and a preferred time/,
    suggestLead: true,
  },
  {
    id: "human",
    question: "I want to talk to a person",
    expect: /front desk/,
    handoff: true,
  },
  {
    id: "out-of-scope",
    question: "Do you treat dogs with veterinary dental surgery?",
    expect: /don't have that/i,
    low: true,
  },
  {
    id: "filling",
    question: "How much does a tooth-colored filling start at?",
    expect: /\$220/,
  },
  {
    id: "portion",
    question: "Will you confirm my insurance portion before treatment?",
    expect: /portion before treatment/,
  },
  {
    id: "child-age",
    question: "At what age do you see children?",
    expect: /age 3/,
  },
];
