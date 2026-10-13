import { createFileRoute, Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { Logo } from '@/components/brand/logo'

export const Route = createFileRoute('/privacy')({ component: PrivacyPage })

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="text-xl font-semibold">{title}</h2>
      <div className="mt-2 grid gap-3 text-muted-foreground">{children}</div>
    </section>
  )
}

function PrivacyPage() {
  return (
    <div className="pt-safe">
      <header className="mx-auto flex h-16 max-w-2xl items-center px-safe">
        <Link to="/" aria-label="Mentor Pilot home" className="rounded-lg">
          <Logo />
        </Link>
      </header>
      <main id="main" className="mx-auto max-w-2xl px-safe pt-6 pb-16">
        <h1 className="text-3xl font-semibold">Privacy notice</h1>
        <p className="mt-3 text-muted-foreground">
          Mentor Pilot is built for learners, so we keep this short and collect as little as we
          can. It follows South Africa's Protection of Personal Information Act (POPIA).
        </p>

        <Block title="What we collect">
          <p>
            Your name and email address, so you can log in. Your date of birth, school, grade,
            province, interests and how you like to learn, so your mentor can guide you properly.
            The projects, notes and messages you create here.
          </p>
          <p>
            If you are under 18, the email address of the parent, guardian or teacher who agreed
            to you using Mentor Pilot.
          </p>
        </Block>

        <Block title="What we use it for">
          <p>
            Only to mentor you: to personalise guidance, keep your project history, connect you
            with a human mentor when you ask for one, and keep the service safe. We do not sell
            your information or use it for advertising.
          </p>
        </Block>

        <Block title="AI and your messages">
          <p>
            Your messages are sent to an AI model provider to generate your mentor's replies.
            Messages are checked automatically for safety. Please don't share personal details
            that your project doesn't need, like your home address or phone number.
          </p>
        </Block>

        <Block title="Your rights">
          <p>
            You can download everything we hold about you, correct it, or delete your account at
            any time from your Profile. Deleting your account erases your personal information.
          </p>
        </Block>

        <Block title="Parents, guardians and teachers">
          <p>
            If a learner listed you and you did not agree, or you want their information removed,
            reply to the email we sent you and we will delete it.
          </p>
        </Block>
      </main>
    </div>
  )
}
