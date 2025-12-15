using Azure.AI.Agents.Persistent;
using MicrosoftFoundry.Classic.Common;

namespace MicrosoftFoundry.Classic.Resources;

/// <summary>
/// Custom agent that uses Model Context Protocol (MCP) tools.
/// Uses server-side MCP integration through Azure AI Foundry.
/// </summary>
public sealed class CustomMCPAgent
{
    // TODO: Update these to point to your MCP server
    private const string McpServerLabel = "custom_mcp_server";
    private const string McpServerUrl = "https://app-ext-eus2-mcp-profx-01.azurewebsites.net/mcp";

    private readonly FoundryClientFactory _factory;

    /// <summary>
    /// Initializes a new instance of the <see cref="CustomMCPAgent"/> class.
    /// </summary>
    /// <param name="factory">The Foundry client factory.</param>
    public CustomMCPAgent(FoundryClientFactory factory)
    {
        ArgumentNullException.ThrowIfNull(factory);
        _factory = factory;
    }

    /// <summary>
    /// Runs the custom agent with MCP tools.
    /// </summary>
    /// <param name="cancellationToken">Cancellation token.</param>
    public async Task RunAsync(CancellationToken cancellationToken = default)
    {
        Console.WriteLine("=== Custom MCP Agent ===");
        Console.WriteLine();

        PersistentAgent? agent = null;
        PersistentAgentThread? thread = null;
        var client = _factory.GetClient();

        try
        {
            // Create MCP tool definition pointing to your MCP server
            Console.WriteLine($"Creating MCP tool for {McpServerUrl}...");
            MCPToolDefinition mcpTool = new(serverLabel: McpServerLabel, serverUrl: McpServerUrl);
            // mcpTool.AllowedTools.Add("multiply");
            // mcpTool.AllowedTools.Add("fahrenheit_to_celsius");

            // Create an agent with MCP tools
            Console.WriteLine("Creating agent with MCP tools...");
            agent = await client.Administration.CreateAgentAsync(
                model: _factory.ModelDeploymentName,
                name: "Foundry-Classic-MCP-Custom",
                instructions: """
                    You are a helpful agent that can use MCP tools to assist users.
                    Always use the available MCP tools to answer questions and perform tasks.
                    """,
                tools: [mcpTool],
                cancellationToken: cancellationToken);

            Console.WriteLine($"Agent created: {agent.Name} (ID: {agent.Id})");

            // Create a conversation thread
            thread = await client.Threads.CreateThreadAsync(cancellationToken: cancellationToken);
            Console.WriteLine($"Thread created: {thread.Id}");
            Console.WriteLine();

            // TODO: Update with your sample queries
            var questions = new[]
            {
                "Start data analysis for dataset - NewSampleAnalysis"
            };

            foreach (var question in questions)
            {
                Console.WriteLine($"[User]: {question}");

                // Create message in thread
                await client.Messages.CreateMessageAsync(
                    thread.Id,
                    MessageRole.User,
                    question,
                    cancellationToken: cancellationToken);

                // Set up MCP tool resources with auto-approval and authentication
                string bearerToken = "your_bearer_token_here"; // TODO: Replace with actual token retrieval logic
                var mcpToolResource = new MCPToolResource(McpServerLabel)
                {
                    RequireApproval = new MCPApproval("never") // Auto-approve for demo
                };
                mcpToolResource.UpdateHeader("Authorization", $"Bearer {bearerToken}");
                // mcpToolResource.Headers.Add("Authorization", $"Bearer {bearerToken}");
                var toolResources = mcpToolResource.ToToolResources();

                // Create and run the agent
                ThreadRun run = await client.Runs.CreateRunAsync(thread, agent, toolResources, cancellationToken: cancellationToken);

                // Wait for completion using the factory method
                run = await _factory.WaitForRunCompletionAsync(thread.Id, run.Id, cancellationToken);

                // Check run status
                if (run.Status != RunStatus.Completed)
                {
                    Console.WriteLine($"Run did not complete successfully. Status: {run.Status}");
                    if (run.LastError is not null)
                    {
                        Console.WriteLine($"Error: {run.LastError.Message}");
                    }
                    continue;
                }

                // Display the run steps (MCP tool calls made)
                DisplayRunSteps(client, run);

                // Display the latest response
                await _factory.DisplayLatestResponseAsync(thread.Id, cancellationToken: cancellationToken);

                Console.WriteLine();

                // Handle MCP tool 504 error by adding delay to the application and fetch the API response.

                await client.Messages.CreateMessageAsync(
                    thread.Id,
                    MessageRole.Agent,
                    "Add API response back to the thread before executing the next agent.",
                    cancellationToken: cancellationToken);
            }
        }
        finally
        {
            // Console.WriteLine("Cleaning up resources...");
            // await _factory.CleanupAsync(agent, thread, cancellationToken);
            // Console.WriteLine("Cleanup complete.");
        }
    }

    private static void DisplayRunSteps(PersistentAgentsClient client, ThreadRun run)
    {
        Console.WriteLine("\n=== MCP Tool Calls ===");

        IReadOnlyList<RunStep> runSteps = [.. client.Runs.GetRunSteps(run: run)];

        foreach (var step in runSteps)
        {
            if (step.StepDetails is RunStepToolCallDetails toolCallDetails)
            {
                foreach (var toolCall in toolCallDetails.ToolCalls)
                {
                    if (toolCall is RunStepMcpToolCall mcpToolCall)
                    {
                        Console.WriteLine($"MCP Tool Call: {mcpToolCall.ServerLabel}.{mcpToolCall.Name}");
                        Console.WriteLine($"   Server: {mcpToolCall.ServerLabel}");
                        Console.WriteLine($"   Arguments: {mcpToolCall.Arguments}");
                        Console.WriteLine($"   Output: {(string.IsNullOrEmpty(mcpToolCall.Output) ? "(no output)" : mcpToolCall.Output[..Math.Min(200, mcpToolCall.Output.Length)] + "...")}");
                        Console.WriteLine();
                    }
                }
            }
            else if (step.StepDetails is RunStepActivityDetails activityDetails)
            {
                foreach (var activity in activityDetails.Activities)
                {
                    foreach (var activityFunction in activity.Tools)
                    {
                        Console.WriteLine($"Function: {activityFunction.Key}");
                        Console.WriteLine($"   Description: {activityFunction.Value.Description}");
                        Console.WriteLine();
                    }
                }
            }
        }
    }
}
