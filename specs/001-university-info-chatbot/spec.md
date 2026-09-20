# Feature Specification: University Policy & Process Q&A Chatbot

**Feature Branch**: `001-university-info-chatbot`

**Created**: 2026-09-16

**Status**: Draft

**Input**: User description: "the two .pdf documents and the one .txt file" — synthesized from `Dean_of_Students_Interview.txt`, `Compiled Initial Corpus Review.pdf`, and `Demo Project_ Compiled Interview Notes.pdf`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Get a direct answer to a common policy or deadline question (Priority: P1)

A student has a question about a common university policy or process — adding/dropping a class, academic standing, a grade appeal, a financial aid deadline, or registration — and asks the chatbot instead of hunting across multiple webpages. The chatbot gives a direct, accurate answer sourced from official PNW content, with a link back to the source.

**Why this priority**: This is the core problem stated by the Dean of Students Office: students can't find answers to common questions, information is scattered across webpages and policy documents, and staff spend significant time answering the same repetitive questions. Every interviewed student independently confirmed this is their biggest pain point. This story alone delivers the primary value of the feature.

**Independent Test**: Can be fully tested by asking the chatbot a fixed set of common questions (e.g., "when is the last day to drop a class," "who do I contact about a grade appeal," "what is the financial aid deadline") and verifying each answer is correct, current, and includes a source link — without the chatbot sending the student to another page to keep searching.

**Acceptance Scenarios**:

1. **Given** a student has a common policy question covered by the source corpus, **When** they ask the chatbot in plain language, **Then** the chatbot returns a direct answer plus a citation/link to the official source, without requiring the student to click through additional pages.
2. **Given** a question involves a dated item (e.g., a drop/add deadline or refund percentage that varies by term), **When** the student asks, **Then** the chatbot answers using the current term's data and does not present an expired or superseded date as current.
3. **Given** an answer requires information that is split across a top-level page and its linked sub-pages or attached PDFs (e.g., paying or appealing a parking ticket), **When** the student asks, **Then** the chatbot synthesizes the full step-by-step process into one answer rather than only returning a link to the top-level page.

---

### User Story 2 - Get campus-specific answers when the answer depends on campus (Priority: P2)

A student asks about something that differs between PNW's Hammond and Westville campuses (e.g., course availability, program offerings, or where to complete a process in person). The chatbot recognizes the answer is campus-dependent and asks which campus the student means before answering, rather than giving a generic or wrong answer.

**Why this priority**: The corpus review identified that course/prerequisite data is fragmented across campus tags, and interviewed students independently said that navigating campus-specific information (and different colleges) was confusing. Answering with the wrong campus's information would actively mislead a student, so this is high-value but secondary to the baseline Q&A capability in Story 1.

**Independent Test**: Can be fully tested by asking a question whose correct answer differs by campus (e.g., course availability for a specific course) and verifying the chatbot asks for the student's campus before giving a final answer, then gives the campus-correct answer once specified.

**Acceptance Scenarios**:

1. **Given** a student asks a question whose answer varies by campus, **When** the chatbot does not yet know which campus the student means, **Then** it asks the student to specify Hammond or Westville before answering.
2. **Given** the student has specified their campus, **When** they ask a follow-up campus-dependent question in the same conversation, **Then** the chatbot uses the previously stated campus without asking again.

---

### User Story 3 - Get routed to the right department instead of a wrong or guessed answer (Priority: P3)

A student asks a question the chatbot cannot confidently answer from its source material — for example, a highly personalized issue like a specific registration error tied to their account, or a topic not covered in the source corpus. The chatbot tells the student it cannot answer and directs them to the specific office or department that can help, instead of guessing.

**Why this priority**: The Dean of Students Office stated their biggest concern is that the chatbot must never give students incorrect policy information. Interviewed students separately confirmed that not knowing which department to contact is itself a major pain point, and that personalized issues (e.g., account-specific registration errors) are the hardest to resolve. This story protects against the highest-risk failure mode (confidently wrong answers) but depends on Story 1's answering capability already existing.

**Independent Test**: Can be fully tested by asking a question that is out of scope or personalized/account-specific and verifying the chatbot declines to guess and instead names the correct department or contact and how to reach them.

**Acceptance Scenarios**:

1. **Given** a student asks a question with no matching information in the source corpus, **When** the chatbot processes the question, **Then** it tells the student it does not have that information and identifies the department or contact who can help, rather than fabricating an answer.
2. **Given** a student describes a personalized issue (e.g., an account-specific registration error), **When** they ask the chatbot, **Then** the chatbot does not attempt to diagnose or resolve the individual account issue and instead directs the student to the appropriate office (e.g., Registrar, academic advisor).

---

### Edge Cases

- What happens when two source pages contain conflicting or inconsistent information (e.g., one page shows an updated deadline and another still shows an old one)? The chatbot must not silently pick one at random — it should prefer the most current/official source or acknowledge the conflict and point the student to the department that can confirm.
- How does the chatbot handle a question about information that exists but is only reachable behind a button, pop-up, tab, or expandable section on the source page (not present in the static top-level page content)?
- How does the chatbot handle a question that is entirely outside university policy/process topics (off-topic chit-chat or unrelated subject matter)?
- How does the chatbot handle a question referencing a program, course, or policy that does not exist or cannot be found anywhere in the source corpus?
- What happens when a student's question is ambiguous about which academic level applies (undergraduate vs. graduate), where the answer differs by level (e.g., plan of study requirements)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The chatbot MUST let students ask free-text questions about university policies, rules, deadlines, and processes, and MUST return a direct answer rather than only a list of links.
- **FR-002**: The chatbot MUST answer only from an approved, current corpus of official PNW content (web pages, policy documents, catalogs, and their linked/attached materials) and MUST NOT invent or infer facts not present in that corpus.
- **FR-003**: Every substantive answer MUST include a citation or link identifying the specific source page(s) or document(s) it was derived from.
- **FR-004**: When a question's correct answer depends on which campus (Hammond or Westville) the student is asking about, the chatbot MUST ask the student to specify their campus before giving a final answer.
- **FR-005**: When a question involves term-specific dated information (deadlines, drop/add dates, refund percentages), the chatbot MUST use the data for the current academic term and MUST NOT present an expired or superseded date/value as current.
- **FR-006**: When source content needed to answer a question is spread across a top-level page, its child links, and attached documents (e.g., parking ticket payment/appeal), the chatbot MUST synthesize a single complete answer covering all the steps, rather than pointing the student to the top-level page to continue searching.
- **FR-007**: When source content is organized as complex tables (e.g., academic-schedule deadline tables by term), the chatbot MUST preserve row/column relationships when answering so that dates, terms, and values are not mismatched.
- **FR-008**: When the chatbot cannot find a confident answer in its source corpus, it MUST tell the student it does not have the answer and MUST identify the specific department, office, or contact who can help, rather than guessing or fabricating a policy answer.
- **FR-009**: The chatbot MUST NOT attempt to perform or complete personalized, account-specific actions or diagnoses (e.g., resolving an individual student's registration error, filling out their plan of study) and MUST instead direct the student to the appropriate office for personalized help.
- **FR-010**: When source pages provide fragmented course/prerequisite information (split across pop-ups, expandable sections, or campus tags), the chatbot MUST combine that information into a single clear summary for the student.

### Key Entities

- **Source Document**: A piece of official PNW content ingested into the chatbot's knowledge base — a web page, PDF, or linked/attached sub-page — including its campus association (if any), term/date applicability, and last-updated information.
- **Student Question / Conversation**: A student's free-text question and the resulting conversation turns, including any clarifying context the student has provided (e.g., stated campus, academic level).
- **Answer**: A response returned to the student, composed of synthesized text plus one or more citations pointing back to the Source Document(s) it was derived from.
- **Department/Contact**: An office or role (e.g., Registrar, Financial Aid, academic advisor, Dean of Students) that the chatbot can direct a student to when it cannot answer a question itself.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Students get an answer to a common policy/deadline question directly in the chat, in under 2 minutes, without needing to visit or search a separate webpage.
- **SC-002**: When tested against a representative set of common questions (add/drop, academic standing, grade appeals, financial aid deadlines, registration, contacts), at least 95% of chatbot answers match official current policy with no factual errors.
- **SC-003**: 100% of the time the chatbot does not have a confident answer, it names a specific department or contact rather than presenting a guessed or fabricated answer.
- **SC-004**: At least 90% of test questions whose answer depends on campus (Hammond vs. Westville) result in the chatbot asking for or correctly using the campus before giving a final answer.
- **SC-005**: In usability testing, at least 80% of student participants rate the chatbot's answers as accurate, current, and easy to understand.
- **SC-006**: Repetitive questions to Dean of Students Office staff on the covered topics measurably decrease after rollout, as reported by office staff.

## Assumptions

- The chatbot answers general, publicly available university policy and process information; it does not require the student to log in and does not access or act on an individual student's private academic record. This matches feedback from an interviewed graduate student that the chatbot "should probably just support general information" rather than performing scheduling or account-specific actions.
- The initial source corpus is built from the PNW web pages and policy PDFs already identified in corpus review (e.g., parking regulations, academic schedule, academic catalog/prerequisites, student handbook, classroom behavior policy, academic integrity policy, accessibility policy, information services policies) plus any pages/documents the Dean of Students Office and Student Service Coordinator identify as covering the most common student questions.
- The chatbot is a text-based conversational interface (chat window), consistent with how students currently interact with the existing "Leo" chatbot and other university chat tools.
- English-language support only for the initial release.
- The source corpus will be periodically reviewed and refreshed by university staff so that term-specific dates (deadlines, refund percentages) stay current; the chatbot itself is not responsible for independently verifying real-world policy changes outside its ingested corpus.
- Launch scope covers the full range of topics identified across the source materials — the Dean of Students Office's named topics (add/drop, academic standing, grade appeals, financial aid deadlines, registration, department contacts) plus the additional topics identified in the corpus review (parking, academic catalog/prerequisites, student handbook, classroom behavior, academic integrity, accessibility, information services policies) — rather than a narrower pilot subset, since no scope restriction was requested.
- This feature is a new, standalone chatbot. It is not required to integrate with, replace, or reuse the existing "Leo" chatbot referenced by an interviewed student, though that relationship may be revisited later.
- When the chatbot hands a student off to a department, the handoff is informational only (naming the office/contact and how to reach them, e.g., link, email, or phone) — it does not create support tickets or connect the student to a live agent within this feature.
