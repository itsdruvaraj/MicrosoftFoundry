using Azure.AI.Agents.Persistent;
using MicrosoftFoundry.Classic.Common;

namespace MicrosoftFoundry.Classic.Resources;

/// <summary>
/// Demonstrates an agent that uses Model Context Protocol (MCP) tools to search Microsoft Learn documentation.
/// Uses server-side MCP integration through Azure AI Foundry.
/// </summary>
public sealed class MicrosoftLearnAgent
{
    private const string McpServerLabel = "search_mslearn_docs";
    private const string McpServerUrl = "https://learn.microsoft.com/api/mcp";

    private readonly FoundryClientFactory _factory;

    /// <summary>
    /// Initializes a new instance of the <see cref="MicrosoftLearnAgent"/> class.
    /// </summary>
    /// <param name="factory">The Foundry client factory.</param>
    public MicrosoftLearnAgent(FoundryClientFactory factory)
    {
        ArgumentNullException.ThrowIfNull(factory);
        _factory = factory;
    }

    /// <summary>
    /// Runs an agent with Microsoft Learn MCP tools.
    /// </summary>
    /// <param name="cancellationToken">Cancellation token.</param>
    public async Task RunAsync(CancellationToken cancellationToken = default)
    {
        Console.WriteLine("=== MCP Agent Example: Microsoft Learn ===");
        Console.WriteLine();

        PersistentAgent? agent = null;
        PersistentAgentThread? thread = null;
        var client = _factory.GetClient();

        try
        {
            // Create MCP tool definition pointing to Microsoft Learn MCP server
            Console.WriteLine($"Creating MCP tool for {McpServerUrl}...");
            var mcpTool = new MCPToolDefinition(serverLabel: McpServerLabel, serverUrl: McpServerUrl);

            // Create an agent with MCP tools
            Console.WriteLine("Creating agent with MCP tools...");
            agent = await client.Administration.CreateAgentAsync(
                model: _factory.ModelDeploymentName,
                name: "Foundry-Classic-MCP-Microsoft-Learn",
                instructions: """
                    You are a helpful agent that can use MCP tools to assist users.
                    Always use the available MCP tools to answer questions and perform tasks.
                    When searching for information, provide comprehensive and accurate responses
                    based on the official Microsoft documentation.
                    Be concise and cite the sources when providing information.
                    """,
                tools: [mcpTool],
                cancellationToken: cancellationToken);

            Console.WriteLine($"Agent created: {agent.Name} (ID: {agent.Id})");

            // Create a conversation thread
            thread = await client.Threads.CreateThreadAsync(cancellationToken: cancellationToken);
            Console.WriteLine($"Thread created: {thread.Id}");
            Console.WriteLine();

            // Demonstrate MCP functionality with sample queries
            var questions = new[]
            {
                "How to connect to Cosmos DB via Python SDK?",
                "What is Azure AI Foundry and how do I create an agent?"
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

                // Set up MCP tool resources with auto-approval
                var mcpToolResource = new MCPToolResource(McpServerLabel)
                {
                    RequireApproval = new MCPApproval("never") // Auto-approve for demo
                };
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
            }
        }
        finally
        {
            Console.WriteLine("Cleaning up resources...");
            await _factory.CleanupAsync(agent, thread, cancellationToken);
            Console.WriteLine("Cleanup complete.");
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
