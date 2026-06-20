workspace "ai-usage" "C4 model for the cross-provider AI usage reporting CLI." {
    model {
        operator = person "Operator" "Runs ai-usage from a shell to inspect provider balances, spend, subscription quotas, token usage, and local history."

        aiUsage = softwareSystem "ai-usage" "Python CLI that collects cross-provider balance, spend, quota, and token-usage data, normalizes it, stores snapshots, and renders table or JSON output." {
            cliProcess = container "CLI process" "Argparse-driven command process exposed as ai_usage.cli:main and the ai-usage console script." "Python 3.10+ CLI" {
                commandRouter = component "Command router" "Parses CLI flags, validates provider selection, chooses live-fetch vs history mode, and coordinates output." "ai_usage.cli"
                credentialLoader = component "Credential loader" "Loads API keys, browser-session cookies, timeout settings, OAuth state references, and Hermes Codex credential-pool accounts from local files and environment variables." "ai_usage.config"
                providerRegistry = component "Provider registry" "Registers and constructs Provider subclasses for DeepSeek, xAI, OpenRouter, Vast.ai, Exa, X API, Codex, Claude Code, Nous, and Google AI Studio." "ai_usage.providers"
                fetchOrchestrator = component "Fetch orchestrator" "Runs selected provider fetches sequentially or concurrently with a total timeout and per-provider error isolation." "ai_usage.fetcher"
                providerAdapters = component "Provider adapters" "Provider-specific modules convert raw HTTP, local CLI, and local file responses into normalized ProviderData." "src/ai_usage/providers"
                httpClient = component "HTTP client" "urllib-based JSON client with timeout, retry, and non-retryable status handling." "ai_usage.http.HttpClient"
                normalizedModels = component "Normalized data model" "ProviderData and TokenData dataclasses for balances, spend, tokens, per-model rows, provider extras, and meta errors." "ai_usage.models"
                snapshotRepository = component "Snapshot repository" "Creates, writes, and queries the local SQLite history database." "ai_usage.db.SnapshotDB"
                renderer = component "Renderer" "Formats normalized live or history data as aligned terminal tables or JSON." "ai_usage.render"
            }

            historyDb = container "Snapshot history database" "Stores normalized provider snapshots for --history queries; raw provider payloads are not stored." "SQLite WAL file at ~/.hermes/ai-usage.db" "Database"
        }

        localCredentialFiles = softwareSystem "Local credential files" "Credential and OAuth state outside the repo: ~/.hermes/.env, ~/.config/vastai/vast_api_key, ~/.hermes/auth.json including credential_pool.openai-codex, ~/.hermes/auth/google_oauth.json, ~/.claude/.credentials.json, ~/.claude.json, and ~/.claude/stats-cache.json." {
            tags "External", "Data Store"
        }
        localCliTools = softwareSystem "Local developer CLIs" "Codex CLI app-server/login fallback and Claude Code CLI refresh paths used for subscription quota and OAuth refresh behavior." {
            tags "External"
        }
        providerHttpApis = softwareSystem "Provider HTTP APIs" "External APIs for DeepSeek, xAI, OpenRouter, Vast.ai, Exa, X Console, Codex usage, Anthropic OAuth usage, Nous Portal, Google OAuth, and Google Cloud Code entitlement/quota data." {
            tags "External"
        }
        terminalOutput = softwareSystem "Terminal / calling process" "Receives stdout table or JSON output from ai-usage." {
            tags "External"
        }

        operator -> aiUsage "Requests current usage or history reports" "shell"
        operator -> cliProcess "Invokes ai-usage commands" "shell"
        operator -> commandRouter "Runs ai-usage commands" "shell"

        aiUsage -> providerHttpApis "Fetches balances, spend, quota, and token usage" "HTTPS"
        aiUsage -> localCredentialFiles "Reads credentials and OAuth state" "filesystem"
        aiUsage -> localCliTools "Delegates CLI-backed quota/auth flows" "subprocess"
        cliProcess -> localCredentialFiles "Reads credentials and OAuth state" "filesystem"
        cliProcess -> localCliTools "Starts Codex fallback and Claude helper commands when required" "subprocess"
        cliProcess -> providerHttpApis "Calls provider APIs through adapters" "HTTPS"
        cliProcess -> historyDb "Writes and reads snapshots" "sqlite3"
        cliProcess -> terminalOutput "Prints table or JSON reports" "stdout"

        commandRouter -> credentialLoader "Loads credentials for live fetch mode"
        commandRouter -> providerRegistry "Builds requested provider set"
        commandRouter -> fetchOrchestrator "Runs live fetch mode"
        commandRouter -> snapshotRepository "Queries history mode"
        commandRouter -> renderer "Renders selected output format"
        credentialLoader -> localCredentialFiles "Reads .env, key files, and OAuth JSON" "filesystem"
        providerRegistry -> providerAdapters "Constructs registered Provider subclasses"
        fetchOrchestrator -> providerAdapters "Invokes fetch() concurrently with timeout isolation" "ThreadPoolExecutor"
        providerAdapters -> httpClient "Use shared JSON client for HTTP providers"
        providerAdapters -> localCliTools "Spawn app-server/login or refresh commands" "subprocess"
        providerAdapters -> localCredentialFiles "Read provider-specific local auth files" "filesystem"
        providerAdapters -> providerHttpApis "Fetch provider-specific data" "HTTPS"
        providerAdapters -> normalizedModels "Return ProviderData and TokenData"
        httpClient -> providerHttpApis "GET/POST JSON with retries and timeouts" "HTTPS"
        snapshotRepository -> historyDb "Insert and query normalized snapshots" "sqlite3"
        renderer -> normalizedModels "Formats normalized results"
        renderer -> terminalOutput "Writes table or JSON" "stdout"
    }

    views {
        systemContext aiUsage "SystemContext" {
            description "C1: ai-usage in its local workstation and provider-account ecosystem."
            include operator
            include aiUsage
            include providerHttpApis
            include localCredentialFiles
            include localCliTools
            include terminalOutput
            autoLayout lr
        }

        container aiUsage "Containers" {
            description "C2: runtime containers and local data store for ai-usage."
            include operator
            include cliProcess
            include historyDb
            include providerHttpApis
            include localCredentialFiles
            include localCliTools
            include terminalOutput
            autoLayout lr
        }

        component cliProcess "CliComponents" {
            description "C3: source-level components inside the Python CLI process."
            include *
            autoLayout lr
        }

        dynamic cliProcess "LiveFetchFlow" {
            description "Live fetch sequence for ai-usage [-p providers] [-m] [-j]."
            operator -> commandRouter "Runs ai-usage with provider/output flags"
            commandRouter -> credentialLoader "Load credentials and timeout settings"
            commandRouter -> providerRegistry "Select selected provider adapters"
            commandRouter -> fetchOrchestrator "Fetch selected providers"
            fetchOrchestrator -> providerAdapters "Call provider.fetch()"
            providerAdapters -> httpClient "Use retrying HTTP client when applicable"
            providerAdapters -> providerHttpApis "Fetch raw balance/spend/quota/token data"
            providerAdapters -> localCliTools "Use CLI-backed quota/auth fallback flows when applicable" "subprocess"
            providerAdapters -> normalizedModels "Normalize raw responses"
            commandRouter -> snapshotRepository "Save fetched snapshot rows"
            snapshotRepository -> historyDb "Insert normalized rows"
            commandRouter -> renderer "Render table or JSON"
            renderer -> terminalOutput "Write final report"
            autoLayout lr
        }

        dynamic cliProcess "HistoryFlow" {
            description "History query sequence for ai-usage --history."
            operator -> commandRouter "Runs ai-usage --history"
            commandRouter -> snapshotRepository "Query provider snapshots"
            snapshotRepository -> historyDb "Read newest rows"
            commandRouter -> renderer "Render history table or JSON"
            renderer -> terminalOutput "Write history report"
            autoLayout lr
        }

        styles {
            element "Person" {
                shape Person
                background #dbeafe
                color #111827
                stroke #2563eb
            }
            element "Software System" {
                background #dcfce7
                color #111827
                stroke #16a34a
            }
            element "Container" {
                background #e0f2fe
                color #111827
                stroke #0284c7
            }
            element "Component" {
                background #f0fdf4
                color #111827
                stroke #22c55e
            }
            element "Database" {
                shape Cylinder
                background #fef3c7
                color #111827
                stroke #d97706
            }
            element "Data Store" {
                shape Cylinder
                background #fef3c7
                color #111827
                stroke #d97706
            }
            element "External" {
                background #f3e8ff
                color #111827
                stroke #9333ea
            }
            relationship "Relationship" {
                color #475569
                thickness 2
            }
        }
    }
}
