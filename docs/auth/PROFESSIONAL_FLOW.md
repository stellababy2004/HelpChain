# HelpChain — Professional Flow (Current State)

## Purpose

This document defines the current canonical professional access flow in HelpChain.

## 1. ProfessionalLead

ProfessionalLead represents an external professional interest, access request, or onboarding lead.

It is:
- not an authenticated admin actor
- not a volunteer
- not yet a standalone professional login account

It is used for:
- intake
- qualification
- review
- approval / rejection
- follow-up tracking

## 2. Admin Review

Professional access requests are reviewed through admin-controlled surfaces.

Canonical review actions include:
- review
- approve
- reject

Professional access is not an open self-service login flow.

## 3. Intervenant

Intervenant represents an approved operational professional actor.

It is the post-approval operational record used in coordination workflows.

Current canonical state:
- Intervenant is an approved operational entity
- Intervenant is not yet documented as a standalone authenticated login actor

## 4. Current rule

Professional onboarding exists.
Professional authentication as a separate login family does not yet exist.

Therefore:
- professionals do not use volunteer login
- professionals do not use admin login
- professional approval is required before operational use

## 5. Future evolution

A future version may introduce a dedicated professional authenticated area.

If implemented, the canonical transition should be:

ProfessionalLead -> admin approval -> Intervenant -> dedicated professional auth account

This must only be introduced with:
- explicit permission model
- tenant / structure scoping
- visibility rules
- post-login destination
- enforcement tests