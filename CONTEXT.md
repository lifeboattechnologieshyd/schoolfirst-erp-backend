# SamsR

SamsR is a family coordination product that combines household membership, document sharing, calendar planning, and AI-assisted conversations. This file fixes the domain language so code, tests, and architecture reviews use the same words for the same concepts.

## Language

### People & Membership

**User**:
A registered person who owns their profile, personal content, and collaboration spaces.
_Avoid_: Account, person

**Family**:
A household-style collaboration group owned by one User.
_Avoid_: Team, group

**Family Member**:
A person's participation in a Family, including relation, role, and invited or joined lifecycle.
_Avoid_: Member, contact

**Close Group**:
A User's smaller trusted circle that is separate from Family membership.
_Avoid_: Family, team, inner circle

**Close Group Member**:
A person's participation in a Close Group with its own invitation lifecycle.
_Avoid_: Member, family member

**Membership Application**:
A request to join the SamsR product that an internal admin reviews.
_Avoid_: Invitation, family invite

**Invitation Code**:
A limited-use code that authorizes signup into the product.
_Avoid_: Membership application, invite link

### Planning & Conversation

**Event**:
A calendar entry anchored to a start time and optionally recurring.
_Avoid_: Meeting, appointment

**Task**:
A calendar work item with status, visibility, and an optional deadline.
_Avoid_: Todo, reminder

**Occurrence**:
One dated instance of a recurring Event or Task, whether virtual or stored as an override.
_Avoid_: Instance row, recurrence row

**Assistant Thread**:
A persistent AI conversation owned by one User.
_Avoid_: Chat, session

**Message**:
A single turn inside an Assistant Thread, including text and tool-call blocks.
_Avoid_: Comment, reply

**Access Policy**:
The rules attached to an Event or Task that determine which other Users can view it, expressed as an access type (only_me, all, mixed) and explicit lists of Family IDs, Close Group IDs, and User IDs.
_Avoid_: Permissions, visibility settings, sharing rules

### Documents & Sharing

**Docusafe Folder**:
A User-owned container for Docusafe Files.
_Avoid_: Directory, bucket

**Docusafe File**:
A stored document or media item tracked inside one Docusafe Folder.
_Avoid_: Attachment, blob

**Access Grant**:
An authenticated Docusafe permission that shares a Docusafe File with a Family or a specific User.
_Avoid_: Share link, temporary share

**Temporary Share**:
A password-protected, expiring public link that can include multiple Docusafe Files across folders.
_Avoid_: Access grant, invitation

## Relationships

- A **User** may own many **Families**, many **Close Groups**, many **Docusafe Folders**, many **Events**, many **Tasks**, and many **Assistant Threads**
- A **Family** has exactly one owner and many **Family Members**
- A **Close Group** is owned by one **User**; a **User** may own many **Close Groups** (currently auto-creates exactly one named "Default")
- A **Docusafe Folder** contains many **Docusafe Files**
- An **Access Grant** applies to one **Docusafe File** and grants visibility to either one **Family** or one **User**
- A **Temporary Share** may include many **Docusafe Files** and does not require a **Family Member** or **Close Group Member** relationship
- An **Occurrence** comes from one recurring **Event** or **Task**
- An **Assistant Thread** contains many **Messages**
- A **Membership Application** concerns product admission and does not by itself create a **Family Member** or **Close Group Member** relationship

## Example dialogue

> **Dev:** "If a cousin needs a passport scan for two days, should I add them as a **Family Member** and create an **Access Grant**, or send a **Temporary Share**?"
> **Domain expert:** "Use an **Access Grant** only when that person should operate inside the authenticated **Family** or **User** context; use a **Temporary Share** for an expiring password-protected link that does not change membership."
>
> **Dev:** "And if the item is a recurring chore, is each visible date a new **Task**?"
> **Domain expert:** "No. Each visible date is an **Occurrence** of the **Task**, and only exceptions become stored overrides."

## Flagged ambiguities

- "share" was used to mean both **Access Grant** and **Temporary Share** — resolved: authenticated internal sharing is an **Access Grant**; public expiring link sharing is a **Temporary Share**
- "member" was used to mean both **Family Member** and **Close Group Member** — resolved: always qualify the membership type
- "group" was used to mean both **Family** and **Close Group** — resolved: **Family** is the household collaboration context; **Close Group** is a User's smaller trusted circle
- "chat" was used to mean both the UI conversation and the stored **Assistant Thread** — resolved: backend and architecture docs use **Assistant Thread** for the persisted conversation and **Message** for each turn
