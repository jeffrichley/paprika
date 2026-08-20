---
name: setup
description: Use when the user wants to start using Paprika from here, mentions connecting or signing in to their Paprika account, says setup is not finished, or when any recipe or meal request fails because this machine has no Paprika sign-in yet.
---

# Setting Paprika up

Getting one person's Paprika account connected to this machine, in plain English,
for someone who does not write software and should never have to.

**She is not a developer.** She has never seen a config file and does not want
to. Nothing you say here may contain a file path, a folder name, a command, a
field name, or any word that only means something to a programmer. If a sentence
would only make sense to somebody who writes software, it is the wrong sentence.

## The shape of it

Three things have to happen, in this order. Run `paprika status` first and do
only what is left — she may have done some of this already, and making her
repeat it is the fastest way to lose her.

1. **Ask for her Paprika email and password.** One at a time, in the
   conversation.
2. **Save them**, then check they work.
3. **Copy her recipes down to this machine.** This is the slow part. Tell her
   how long before you start it.

## Reading `paprika status`

It answers with a `setup` value. Do a different thing for each:

| `setup` | What it means | What to do |
| --- | --- | --- |
| `never_set_up` | Nothing done yet | Start at step 1 |
| `incomplete` | Some of it is done | Read `still_to_do` and do only those |
| `set_up` | Already finished | Say so in one line and stop. Do not redo it |
| `unreadable` | Something here is damaged | **Stop.** See *When it is damaged* below |

`still_to_do` names what is left. `credentials` means she has not given her
sign-in; `signed_in` means it has not been checked; `library` means her recipes
have not been copied down yet.

## Step 1 — her sign-in

Ask for the email first, then the password. Say plainly, once, that this is the
same email and password she uses to sign in to Paprika itself, and that it is
kept on this computer so she does not have to type it again.

**Do not** explain where it is kept, or in what. She does not need to know and
telling her is noise.

## Step 2 — save it and check it

Save it with the password on standard input — never as part of the command
itself:

```bash
printf '%s' "$PASSWORD" | paprika setup credentials --email "$EMAIL" --password-stdin
```

Then run `paprika login`.

If that comes back with `ok: false`, say what the message says, in your own
words, and offer to try the email and password again. **Do not** show her the
code, the exit status, or anything else from the response. Almost always she has
mistyped something, so ask rather than diagnose.

## Step 3 — copy her recipes down

**Tell her how long it will take before you start.** `paprika status` returns
`estimated_seconds`. Turn it into round, human language — "about two minutes",
"three or four minutes" — and never repeat the number back as a number.

Say two things and then start:

- roughly how long it will be
- that it only happens once, and that closing the laptop partway is safe

Then run `paprika sync`.

If it stops partway — she interrupts it, the machine sleeps, anything — running
`paprika sync` again picks up from where it stopped. It does not start over.
Tell her that plainly if it happens; do not apologise for it at length.

## When it is done

One or two sentences. What she can do now, not what you did.

> That's everything — your recipes are here now. You can ask me to plan a week,
> find something to cook, or tidy up your library whenever you like.

Do not list what you ran. Do not summarise the steps. Do not offer a tour.

## When it is damaged

If `setup` comes back `unreadable`, something on this machine is broken rather
than missing — and she may well have been using this happily for months.

**Do not tell her she has never set this up, and do not start setup over.** Say
that something here looks damaged, that her recipes in Paprika itself are
untouched and safe, and point her at `/paprika:help`.

## Rules that do not bend

- **Never invent a reason for a failure.** Say what the message said, in plainer
  words. If you do not know why, say you do not know.
- **Never show her a code, a status, a path, or anything in brackets.** If a
  response contains something you cannot say in a sentence to a person who does
  not write software, do not say it at all.
- **Never ask her to open, create or edit a file.** If setup cannot be finished
  from this conversation, that is a bug, not something to hand to her.
- **Never say it is set up until `paprika status` says so.** Not "that should
  do it", not "I think we're there". Check, then say.
- **Her password appears once, in the moment she types it.** Never repeat it
  back, never put it in a command, never show it in a summary.

## Common mistakes

| Mistake | Instead |
| --- | --- |
| Starting the download with no warning | Say how long, then start |
| Repeating setup because she asked about Paprika | Check `status` first; if `set_up`, say so and stop |
| Treating `unreadable` as `never_set_up` | Four answers, not two. Damaged is not new |
| Explaining where things are kept | She does not need to know |
| Reading out the response | Say the one thing that matters, in a sentence |
| Asking her to fix something by hand | Setup finishes here or it is our bug |
