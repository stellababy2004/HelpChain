--
-- PostgreSQL database dump
--

\restrict NDXqnh4ZbeQLfMXwUVRSdCtjlWEr9XB3IzFq8U9gf5rXIdPdqaDBedc4UCKxAi0

-- Dumped from database version 17.8 (6108b59)
-- Dumped by pg_dump version 17.8 (Debian 17.8-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: admin_users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admin_users (
    id integer NOT NULL,
    username character varying(80) NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    role character varying(32) DEFAULT 'admin'::character varying,
    is_active boolean DEFAULT true,
    totp_secret character varying(32),
    mfa_enabled boolean DEFAULT false,
    mfa_enrolled_at timestamp without time zone,
    backup_codes_hashes text,
    backup_codes_generated_at timestamp without time zone
);


--
-- Name: admin_users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.admin_users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: admin_users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.admin_users_id_seq OWNED BY public.admin_users.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: email_send_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.email_send_events (
    id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    email_hash character varying(64) NOT NULL,
    purpose character varying(64) NOT NULL,
    outcome character varying(16) NOT NULL,
    reason character varying(64),
    ip character varying(64),
    ua character varying(256)
);


--
-- Name: email_send_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.email_send_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: email_send_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.email_send_events_id_seq OWNED BY public.email_send_events.id;


--
-- Name: requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.requests (
    id integer NOT NULL,
    title character varying NOT NULL,
    description text,
    name character varying(200),
    email character varying(200),
    phone character varying(50),
    city character varying(200),
    region character varying(200),
    location_text character varying(500),
    message text,
    status character varying(50),
    priority character varying(50),
    category character varying(32) DEFAULT 'general'::character varying NOT NULL,
    source_channel character varying(100),
    assigned_volunteer_id integer,
    completed_at timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    latitude double precision,
    longitude double precision,
    user_id integer,
    owner_id integer,
    owned_at timestamp without time zone,
    requester_token_hash character varying(128),
    requester_token_created_at timestamp without time zone,
    is_archived boolean DEFAULT false NOT NULL,
    archived_at timestamp without time zone,
    deleted_at timestamp without time zone
);


--
-- Name: requests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.requests_id_seq OWNED BY public.requests.id;


--
-- Name: volunteer_match_feedback; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.volunteer_match_feedback (
    id integer NOT NULL,
    volunteer_id integer NOT NULL,
    request_id integer NOT NULL,
    action character varying(20) NOT NULL,
    expires_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: volunteer_match_feedback_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.volunteer_match_feedback_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: volunteer_match_feedback_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.volunteer_match_feedback_id_seq OWNED BY public.volunteer_match_feedback.id;


--
-- Name: volunteer_request_states; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.volunteer_request_states (
    id integer NOT NULL,
    volunteer_id integer NOT NULL,
    request_id integer NOT NULL,
    seen_at timestamp without time zone,
    dismissed_until timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


--
-- Name: volunteer_request_states_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.volunteer_request_states_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: volunteer_request_states_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.volunteer_request_states_id_seq OWNED BY public.volunteer_request_states.id;


--
-- Name: volunteers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.volunteers (
    id integer NOT NULL,
    name character varying(120) NOT NULL,
    email character varying(120) NOT NULL,
    phone character varying(20),
    location character varying(100),
    latitude double precision,
    longitude double precision
);


--
-- Name: volunteers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.volunteers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: volunteers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.volunteers_id_seq OWNED BY public.volunteers.id;


--
-- Name: admin_users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users ALTER COLUMN id SET DEFAULT nextval('public.admin_users_id_seq'::regclass);


--
-- Name: email_send_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_send_events ALTER COLUMN id SET DEFAULT nextval('public.email_send_events_id_seq'::regclass);


--
-- Name: requests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requests ALTER COLUMN id SET DEFAULT nextval('public.requests_id_seq'::regclass);


--
-- Name: volunteer_match_feedback id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.volunteer_match_feedback ALTER COLUMN id SET DEFAULT nextval('public.volunteer_match_feedback_id_seq'::regclass);


--
-- Name: volunteer_request_states id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.volunteer_request_states ALTER COLUMN id SET DEFAULT nextval('public.volunteer_request_states_id_seq'::regclass);


--
-- Name: volunteers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.volunteers ALTER COLUMN id SET DEFAULT nextval('public.volunteers_id_seq'::regclass);


--
-- Data for Name: admin_users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.admin_users (id, username, email, password_hash, role, is_active, totp_secret, mfa_enabled, mfa_enrolled_at, backup_codes_hashes, backup_codes_generated_at) FROM stdin;
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
b2d5c3f1a9e0
\.


--
-- Data for Name: email_send_events; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.email_send_events (id, created_at, email_hash, purpose, outcome, reason, ip, ua) FROM stdin;
1	2026-02-18 12:21:01.894725+00	572c392c7c7f6f429731c9758c59e3925ee44fbb4176d706643d551e7fd97bc0	request_magic_link	failed	smtp_error	176.187.72.236	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0
2	2026-02-18 12:22:10.42417+00	572c392c7c7f6f429731c9758c59e3925ee44fbb4176d706643d551e7fd97bc0	request_magic_link	failed	smtp_error	176.187.72.236	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0
3	2026-02-18 12:22:25.492916+00	572c392c7c7f6f429731c9758c59e3925ee44fbb4176d706643d551e7fd97bc0	request_magic_link	failed	smtp_error	176.187.72.236	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0
4	2026-02-18 12:34:00.841408+00	572c392c7c7f6f429731c9758c59e3925ee44fbb4176d706643d551e7fd97bc0	request_magic_link	failed	smtp_error	176.187.72.236	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0
5	2026-02-18 12:46:26.037879+00	572c392c7c7f6f429731c9758c59e3925ee44fbb4176d706643d551e7fd97bc0	request_magic_link	failed	smtp_error	176.187.72.236	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0
6	2026-02-18 12:46:41.188166+00	572c392c7c7f6f429731c9758c59e3925ee44fbb4176d706643d551e7fd97bc0	request_magic_link	failed	smtp_error	176.187.72.236	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0
7	2026-02-18 12:56:42.988585+00	572c392c7c7f6f429731c9758c59e3925ee44fbb4176d706643d551e7fd97bc0	request_magic_link	failed	smtp_error	176.187.72.236	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0
8	2026-02-18 12:57:40.364065+00	572c392c7c7f6f429731c9758c59e3925ee44fbb4176d706643d551e7fd97bc0	request_magic_link	failed	smtp_error	176.187.72.236	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0
9	2026-02-24 12:21:11.623758+00	9ac4e6116f4066ea89c24f444d300d0562599371f838464fe350aa090fb6358b	request_magic_link	failed	smtp_error	176.187.72.236	Mozilla/5.0 (iPhone; CPU iPhone OS 26_3_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/145.0.7632.108 Mobile/15E148 Safari/604.1
\.


--
-- Data for Name: requests; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.requests (id, title, description, name, email, phone, city, region, location_text, message, status, priority, category, source_channel, assigned_volunteer_id, completed_at, created_at, updated_at, latitude, longitude, user_id, owner_id, owned_at, requester_token_hash, requester_token_created_at, is_archived, archived_at, deleted_at) FROM stdin;
1	médicaments	j'ai besoin des médicaments	Stella Barbarella	san4o_baby@hotmail.com	+33600000000	\N	\N	Paris	\N	pending	medium	medical	\N	\N	\N	2026-02-14 14:33:00.229888	\N	\N	\N	\N	\N	\N	927f8bee2bbf741fc1efe4e4f491c4f5e071873a36faf4808e20286e52092bcf	2026-02-14 14:33:00.089608	f	\N	\N
2	Test	J’ai besoin des médicaments	Stella Barbarella	\N	06600000	\N	\N	Paris	\N	pending	low	medical	\N	\N	\N	2026-02-16 06:27:32.095201	\N	\N	\N	\N	\N	\N	ac17c7d838b0c1a9987addeed5a084fee7ca056a0c9c8b556b964f19e3ea7fb1	2026-02-16 06:27:32.04185	f	\N	\N
3	test test	test test test	Stella Barbarella	san4o_baby@hotmail.com	+33600000001	\N	\N	Paris	\N	pending	low	medical	\N	\N	\N	2026-02-18 12:20:46.716056	\N	\N	\N	\N	\N	\N	325f4b4d1296c532a5c8fcb659045bf98b423a938707baa492e3212b15c7dff2	2026-02-18 12:20:46.583434	f	\N	\N
4	test test	test test test	Stella Barbarella	san4o_baby@hotmail.com	+33600000001	\N	\N	Paris	\N	pending	medium	medical	\N	\N	\N	2026-02-18 12:21:55.391282	\N	\N	\N	\N	\N	\N	6f396a4e67f80a59edbdefe222b119397e1c9eced50fc7d4172155c7db7991b2	2026-02-18 12:21:55.378026	f	\N	\N
5	test test	test test test	Stella Barbarella	san4o_baby@hotmail.com	+33600000001	\N	\N	Paris	\N	pending	medium	medical	\N	\N	\N	2026-02-18 12:22:10.453983	\N	\N	\N	\N	\N	\N	228f705ab8a46ca9bb238bb4b1f771ec3ae4e61b36a7551fa311dac55e37b94b	2026-02-18 12:22:10.441502	f	\N	\N
6	тест ок	трябва да работи вече	Stella Barbarella	san4o_baby@hotmail.com	+33600000001	\N	\N	Paris	\N	pending	medium	medical	\N	\N	\N	2026-02-18 12:33:45.534131	\N	\N	\N	\N	\N	\N	22db80ef728cf4851ee31382c5392ff1c3f3ace403130c61657b440dd442726d	2026-02-18 12:33:45.450317	f	\N	\N
7	тест тест тест	работи ли човек	Stella Barbarella	san4o_baby@hotmail.com	+33600000001	\N	\N	Paris	\N	pending	high	medical	\N	\N	\N	2026-02-18 12:46:10.834393	\N	\N	\N	\N	\N	\N	9681d188f5e979d8ebc9c9cf1ee29aefcbb6d227603b8cc19709c57e76102dca	2026-02-18 12:46:10.807631	f	\N	\N
8	тест тест тест	работи ли човек	Stella Barbarella	san4o_baby@hotmail.com	+33600000001	\N	\N	Paris	\N	pending	high	medical	\N	\N	\N	2026-02-18 12:46:26.136067	\N	\N	\N	\N	\N	\N	15fe6efe3bd90a4bf9eac4db7bb08b059809e083fdb68e567a703fdf7498bb30	2026-02-18 12:46:26.085665	f	\N	\N
9	вече трябва да работи	моля те вече работи	Stella Barbarella	san4o_baby@hotmail.com	+33600000001	\N	\N	Paris	\N	pending	medium	medical	\N	\N	\N	2026-02-18 12:56:27.861634	\N	\N	\N	\N	\N	\N	578308fdf398caba3e230b2e91da2866295bb465987be980197c1e6347da52b7	2026-02-18 12:56:27.713739	f	\N	\N
10	вече трябва да работи 2	моля те работи 2	Stella Barbarella	san4o_baby@hotmail.com	+33600000001	\N	\N	Paris	\N	pending	medium	medical	\N	\N	\N	2026-02-18 12:57:25.315727	\N	\N	\N	\N	\N	\N	f341fef0efa7883c60b9e099d0711c4fdd86b7878cd14a33bfc5545abd774104	2026-02-18 12:57:25.304602	f	\N	\N
11	Нужен ми е придружител	Нямам кола някой да ме закара	Stella Stoyanova	stiliana.stoyanova@orange.fr	+33660708186	\N	\N	12 RUE YVES KERMEN	\N	pending	medium	social	\N	\N	\N	2026-02-24 12:20:56.453061	\N	\N	\N	\N	\N	\N	7861db15652238ebc6a22aae554c0c51668d8b98511b7e85b87c85ce9cfc0a67	2026-02-24 12:20:56.321122	f	\N	\N
\.


--
-- Data for Name: volunteer_match_feedback; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.volunteer_match_feedback (id, volunteer_id, request_id, action, expires_at, created_at) FROM stdin;
\.


--
-- Data for Name: volunteer_request_states; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.volunteer_request_states (id, volunteer_id, request_id, seen_at, dismissed_until, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: volunteers; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.volunteers (id, name, email, phone, location, latitude, longitude) FROM stdin;
\.


--
-- Name: admin_users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.admin_users_id_seq', 1, false);


--
-- Name: email_send_events_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.email_send_events_id_seq', 9, true);


--
-- Name: requests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.requests_id_seq', 11, true);


--
-- Name: volunteer_match_feedback_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.volunteer_match_feedback_id_seq', 1, false);


--
-- Name: volunteer_request_states_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.volunteer_request_states_id_seq', 1, false);


--
-- Name: volunteers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.volunteers_id_seq', 1, false);


--
-- Name: admin_users admin_users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users
    ADD CONSTRAINT admin_users_email_key UNIQUE (email);


--
-- Name: admin_users admin_users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users
    ADD CONSTRAINT admin_users_pkey PRIMARY KEY (id);


--
-- Name: admin_users admin_users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users
    ADD CONSTRAINT admin_users_username_key UNIQUE (username);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: email_send_events email_send_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_send_events
    ADD CONSTRAINT email_send_events_pkey PRIMARY KEY (id);


--
-- Name: requests requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.requests
    ADD CONSTRAINT requests_pkey PRIMARY KEY (id);


--
-- Name: volunteer_match_feedback uq_vol_req_feedback; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.volunteer_match_feedback
    ADD CONSTRAINT uq_vol_req_feedback UNIQUE (volunteer_id, request_id);


--
-- Name: volunteer_request_states uq_volunteer_request_state; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.volunteer_request_states
    ADD CONSTRAINT uq_volunteer_request_state UNIQUE (volunteer_id, request_id);


--
-- Name: volunteer_match_feedback volunteer_match_feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.volunteer_match_feedback
    ADD CONSTRAINT volunteer_match_feedback_pkey PRIMARY KEY (id);


--
-- Name: volunteer_request_states volunteer_request_states_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.volunteer_request_states
    ADD CONSTRAINT volunteer_request_states_pkey PRIMARY KEY (id);


--
-- Name: volunteers volunteers_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.volunteers
    ADD CONSTRAINT volunteers_email_key UNIQUE (email);


--
-- Name: volunteers volunteers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.volunteers
    ADD CONSTRAINT volunteers_pkey PRIMARY KEY (id);


--
-- Name: ix_email_send_events_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_email_send_events_created_at ON public.email_send_events USING btree (created_at);


--
-- Name: ix_email_send_events_email_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_email_send_events_email_hash ON public.email_send_events USING btree (email_hash);


--
-- Name: ix_email_send_events_hash_purpose_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_email_send_events_hash_purpose_created ON public.email_send_events USING btree (email_hash, purpose, created_at);


--
-- Name: ix_email_send_events_purpose; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_email_send_events_purpose ON public.email_send_events USING btree (purpose);


--
-- Name: ix_requests_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_requests_category ON public.requests USING btree (category);


--
-- Name: ix_requests_deleted_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_requests_deleted_at ON public.requests USING btree (deleted_at);


--
-- Name: ix_requests_is_archived; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_requests_is_archived ON public.requests USING btree (is_archived);


--
-- Name: ix_requests_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_requests_owner_id ON public.requests USING btree (owner_id);


--
-- Name: ix_requests_requester_token_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_requests_requester_token_hash ON public.requests USING btree (requester_token_hash);


--
-- Name: ix_volunteer_match_feedback_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_volunteer_match_feedback_request_id ON public.volunteer_match_feedback USING btree (request_id);


--
-- Name: ix_volunteer_match_feedback_volunteer_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_volunteer_match_feedback_volunteer_id ON public.volunteer_match_feedback USING btree (volunteer_id);


--
-- Name: ix_volunteer_request_states_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_volunteer_request_states_request_id ON public.volunteer_request_states USING btree (request_id);


--
-- Name: ix_volunteer_request_states_volunteer_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_volunteer_request_states_volunteer_id ON public.volunteer_request_states USING btree (volunteer_id);


--
-- Name: volunteer_match_feedback volunteer_match_feedback_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.volunteer_match_feedback
    ADD CONSTRAINT volunteer_match_feedback_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.requests(id);


--
-- Name: volunteer_match_feedback volunteer_match_feedback_volunteer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.volunteer_match_feedback
    ADD CONSTRAINT volunteer_match_feedback_volunteer_id_fkey FOREIGN KEY (volunteer_id) REFERENCES public.volunteers(id);


--
-- Name: volunteer_request_states volunteer_request_states_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.volunteer_request_states
    ADD CONSTRAINT volunteer_request_states_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.requests(id);


--
-- Name: volunteer_request_states volunteer_request_states_volunteer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.volunteer_request_states
    ADD CONSTRAINT volunteer_request_states_volunteer_id_fkey FOREIGN KEY (volunteer_id) REFERENCES public.volunteers(id);


--
-- PostgreSQL database dump complete
--

\unrestrict NDXqnh4ZbeQLfMXwUVRSdCtjlWEr9XB3IzFq8U9gf5rXIdPdqaDBedc4UCKxAi0

