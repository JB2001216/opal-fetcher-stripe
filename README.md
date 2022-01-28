<p  align="center">
 <img src="https://i.ibb.co/BGVBmMK/opal.png" height=170 alt="opal" border="0" />
</p>
<h2 align="center">
OPAL Fetcher for Postgres
</h2>

[Check out OPAL main repo here.](https://github.com/permitio/opal)

### What's in this repo?

An
OPAL [custom fetch provider](https://github.com/permitio/opal/blob/master/docs/HOWTO/write_your_own_fetch_provider.md) to
bring authorization state from [Stripe](https://stripe.com/).

This fetcher is both:

- **A fully functional fetch-provider for Stripe:** can be used by OPAL to fetch data from Stripe API.
- **Serving as an example** how to write custom fetch providers for OPAL and how to publish them as pip packages.

### How to try this custom fetcher in few commands? (Example docker-compose configuration)

You can test this fetcher with the example docker compose file in this repository root. Clone this repo, `cd` into the
cloned repo, and then run:

```
echo "STRIPE_API_KEY=YOUR_STRIPE_API_KEY" > .env
docker-compose up
```

This docker-compose configuration already correctly configures OPAL to load the Stripe Fetch Provider, and correctly
configures `OPAL_DATA_CONFIG_SOURCES` to include an entry that uses this fetcher. But for a live test, you need to 
create a Stripe test profile with customers and purchases. 

You can test the rule by running:
```
curl --request POST 'http://localhost:8181/v1/data/app/stripe/allow' --header 'Content-Type: application/json' --data-raw '{"input": {"user": "nopayment@email.test","method": "GET", "url": "blog"}}'
```
Examples for the input data you can find in the `example_input.json` file.

Data for testing on [Playground](https://play.openpolicyagent.org/) you can find in the `example_data.json` file.

Example rules placed in [Example Policy Repo](https://github.com/JB2001216/opal-example-policy-repo)
### How to use this fetcher in your OPAL Setup

#### 1) Build a custom opal-client `Dockerfile`

The official docker image only contains the built-in fetch providers. You need to create your own `Dockerfile` (that is
based on the official docker image), that includes this fetcher's pip package.

Your `Dockerfile` should look like this:

```
FROM authorizon/opal-client:latest
RUN pip install --no-cache-dir --user opal-fetcher-stripe
```

#### 2) Build your custom opal-client container

Say your special Dockerfile from step one is called `custom_client.Dockerfile`.

You must build a customized OPAL container from this Dockerfile, like so:

```
docker build -t yourcompany/opal-client -f custom_client.Dockerfile .
```

#### 3) When running OPAL, set `OPAL_FETCH_PROVIDER_MODULES`

Pass the following environment variable to the OPAL client docker container (comma-separated provider modules):

```
OPAL_FETCH_PROVIDER_MODULES=opal_common.fetcher.providers,opal_fetcher_stripe.provider
```

Notice that OPAL receives a list from where to search for fetch providers. The list in our case includes the built-in
providers (`opal_common.fetcher.providers`) and our custom postgres provider.

#### 4) Using the custom provider in your DataSourceEntry objects

Your DataSourceEntry objects (either in `OPAL_DATA_CONFIG_SOURCES` or in dynamic updates sent via the OPAL publish API)
can now include this fetcher's config.

Example value of `OPAL_DATA_CONFIG_SOURCES` (formatted nicely, but in env var you should pack this to one-line and
no-spaces):

```json
{
  "config": {
    "entries": [
      {
        "url": "Customer",
        "config": {
          "fetcher": "StripeFetchProvider",
          "connection_params": {
            "api_key": "${STRIPE_API_KEY}",
            "max_network_retries": 2,
            "log_level": "info",
            "enable_telemetry": false
          }
        },
        "topics": [
          "policy_data"
        ],
        "dst_path": "users"
      },
      {
        "url": "Invoice",
        "config": {
          "fetcher": "StripeFetchProvider",
          "connection_params": {
            "api_key": "${STRIPE_API_KEY}",
            "max_network_retries": 2,
            "log_level": "info",
            "enable_telemetry": false
          }
        },
        "topics": [
          "policy_data"
        ],
        "dst_path": "user_products"
      },
      {
        "url": "Subscription",
        "config": {
          "fetcher": "StripeFetchProvider",
          "connection_params": {
            "api_key": "${STRIPE_API_KEY}",
            "max_network_retries": 2,
            "log_level": "info",
            "enable_telemetry": false
          }
        },
        "topics": [
          "policy_data"
        ],
        "dst_path": "user_subscriptions"
      },
      {
        "url": "PaymentIntent",
        "config": {
          "fetcher": "StripeFetchProvider",
          "connection_params": {
            "api_key": "${STRIPE_API_KEY}",
            "max_network_retries": 2,
            "log_level": "info",
            "enable_telemetry": false
          }
        },
        "topics": [
          "policy_data"
        ],
        "dst_path": "user_payments"
      }
    ]
  }
}
```

Notice how `config` is an instance of `StripeFetcherConfig` (code is in `opal_fetcher_stripe/provider.py`).

Values for this fetcher config:

* The `url` is actually a Stripe resource.
* `connection_params` are required, your params must include the `api_key` key.
* Your `config` must include the `fetcher` key to indicate to OPAL that you use a custom fetcher.

### About OPAL (Open Policy Administration Layer)

[OPAL](https://github.com/permitio/opal) is an administration layer for Open Policy Agent (OPA), detecting changes to
both policy and policy data in realtime and pushing live updates to your agents.

OPAL brings open-policy up to the speed needed by live applications. As your application state changes (whether it's via
your APIs, DBs, git, S3 or 3rd-party SaaS services), OPAL will make sure your services are always in sync with the
authorization data and policy they need (and only those they need).

Check out OPAL's main site at [OPAL.ac](https://opal.ac).

<img src="https://i.ibb.co/CvmX8rR/simplified-diagram-highlight.png" alt="simplified" border="0">
